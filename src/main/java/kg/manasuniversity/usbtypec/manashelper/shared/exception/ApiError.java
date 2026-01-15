package kg.manasuniversity.usbtypec.manashelper.shared.exception;

import java.util.List;

public record ApiError(
        ApiErrorCode code,
        String message,
        List<FieldError> errors
) {
  public record FieldError(String field, String message) {
  }
}
