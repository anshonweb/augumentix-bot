import discord
import logging

logger = logging.getLogger('discord')

class RoleManager:
    def __init__(self, database):
        self.db = database

        self.role_config = {
            'Gold': {'threshold': 10, 'color': discord.Color.gold()},
            'Silver': {'threshold': 5, 'color': discord.Color.light_gray()},
            'Bronze': {'threshold': 1, 'color': discord.Color.orange()}
        }

    async def update_user_role(self, member: discord.Member, guild: discord.Guild):
        try:
            user = await self.db.get_user(member.id)

            if not user:
                return

            weekly_solved = user['weekly_solved']

            roles_to_add = []
            roles_to_remove = []
            target_role = None

            if weekly_solved >= self.role_config['Gold']['threshold']:
                target_role = 'Gold'
            elif weekly_solved >= self.role_config['Silver']['threshold']:
                target_role = 'Silver'
            elif weekly_solved >= self.role_config['Bronze']['threshold']:
                target_role = 'Bronze'

            all_roles = {}

            for role_name, config in self.role_config.items():
                role = discord.utils.get(guild.roles, name=role_name)

                if not role:
                    try:
                        role = await guild.create_role(
                            name=role_name,
                            color=config['color'],
                            reason="LeetCode bot role"
                        )
                        logger.info(f"Created role: {role_name}")
                    except Exception as e:
                        logger.error(f"Failed to create role {role_name}: {e}")
                        continue

                all_roles[role_name] = role

            if target_role:
                if all_roles[target_role] not in member.roles:
                    roles_to_add.append(all_roles[target_role])

                for role_name, role in all_roles.items():
                    if role_name != target_role and role in member.roles:
                        roles_to_remove.append(role)
            else:
                for role in all_roles.values():
                    if role in member.roles:
                        roles_to_remove.append(role)

            try:
                if roles_to_remove:
                    await member.remove_roles(
                        *roles_to_remove,
                        reason="LeetCode stats update"
                    )
                    logger.info(
                        f"Removed roles from {member.name}: {[r.name for r in roles_to_remove]}"
                    )

                if roles_to_add:
                    await member.add_roles(
                        *roles_to_add,
                        reason="LeetCode stats update"
                    )
                    logger.info(
                        f"Added roles to {member.name}: {[r.name for r in roles_to_add]}"
                    )

            except discord.Forbidden:
                logger.error(f"Missing permissions to manage roles for {member.name}")
            except Exception as e:
                logger.error(f"Error updating roles for {member.name}: {e}")

        except Exception as e:
            logger.error(f"Error in update_user_role: {e}")

    async def update_all_roles(self, bot):
        try:
            users = await self.db.get_all_users()

            for guild in bot.guilds:
                for user_id, _ in users:
                    member = guild.get_member(user_id)
                    if member:
                        await self.update_user_role(member, guild)

            logger.info("Updated roles for all users")

        except Exception as e:
            logger.error(f"Error updating all roles: {e}")
