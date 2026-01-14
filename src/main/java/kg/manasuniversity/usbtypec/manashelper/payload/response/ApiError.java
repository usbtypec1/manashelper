package kg.manasuniversity.usbtypec.manashelper.payload.response;

import kg.manasuniversity.usbtypec.manashelper.enums.ApiErrorCode;

import java.util.List;

public record ApiError(
        ApiErrorCode code,
        String message,
        List<FieldError> errors
) {
  public record FieldError(String field, String message) {
  }
}
