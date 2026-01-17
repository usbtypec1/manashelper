package kg.manasuniversity.usbtypec.manashelper.user.dto.response;

public record UsersStatisticsResponse(
        int totalUsersCount,
        int usersWithCredentialsCount
) {
}
