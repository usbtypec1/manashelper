from manashelper.db.models import User
from manashelper.modules.users.queries import UsersQuery
from manashelper.repositories.user_repository import UserRepository


async def test_users_query_includes_all_users_and_reads_current_database_state(session):
    queries = UsersQuery(UserRepository(session))
    original_ids = await queries.get_all_ids()
    assert await queries.count() == len(original_ids)
    session.add_all([User(id=944_001, full_name="First"), User(id=944_002, full_name="Second")])
    await session.flush()
    assert set(await queries.get_all_ids()) == set(original_ids) | {944_001, 944_002}
    assert await queries.count() == len(original_ids) + 2
