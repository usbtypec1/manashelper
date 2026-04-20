package kg.manasuniversity.usbtypec.manashelper.user.model;

public record UsersStatistics(
    long totalUsersCount,
    long usersWithCredentialsCount,
    int usersWithCredentialsPercentage
) {
}
