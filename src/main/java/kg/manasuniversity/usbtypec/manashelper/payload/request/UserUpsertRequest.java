package kg.manasuniversity.usbtypec.manashelper.payload.request;

public record UserUpsertRequest(
        long id,
        String studentNumber,
        String plainPassword
) {
}
