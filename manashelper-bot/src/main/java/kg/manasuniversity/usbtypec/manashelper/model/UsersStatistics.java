package kg.manasuniversity.usbtypec.manashelper.model;

public record UsersStatistics(
    long totalUsersCount,
    long usersWithCredentialsCount,
    int usersWithCredentialsPercentage
) {
}
