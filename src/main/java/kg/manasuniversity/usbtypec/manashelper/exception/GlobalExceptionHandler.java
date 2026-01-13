package kg.manasuniversity.usbtypec.manashelper.exception;

import kg.manasuniversity.usbtypec.manashelper.enums.ApiErrorCode;
import kg.manasuniversity.usbtypec.manashelper.payload.response.ApiError;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;

@RestControllerAdvice
public class GlobalExceptionHandler {
  private static final Logger log = LoggerFactory.getLogger(GlobalExceptionHandler.class);

  @ExceptionHandler(DepartmentNotFoundException.class)
  public ResponseEntity<ApiError> handleDepartmentNotFound(
          DepartmentNotFoundException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.DEPARTMENT_NOT_FOUND,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
  }

  @ExceptionHandler(FacultyNotFoundException.class)
  public ResponseEntity<ApiError> handleFacultyNotFound(
          FacultyNotFoundException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.FACULTY_NOT_FOUND,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
  }

  @ExceptionHandler(CourseNotFoundException.class)
  public ResponseEntity<ApiError> handleCourseNotFound(
          CourseNotFoundException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.COURSE_NOT_FOUND,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
  }

  @ExceptionHandler(UserNotFoundException.class)
  public ResponseEntity<ApiError> handleUserNotFound(
          UserNotFoundException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.USER_NOT_FOUND,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
  }

  @ExceptionHandler(UserHasNoCredentialsException.class)
  public ResponseEntity<ApiError> handleUserHasNoCredentials(
          UserHasNoCredentialsException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.USER_HAS_NO_CREDENTIALS,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(apiError);
  }

  @ExceptionHandler(MethodArgumentNotValidException.class)
  public ResponseEntity<ApiError> handleValidation(
          MethodArgumentNotValidException ex
  ) {
    List<ApiError.FieldError> fields = ex.getBindingResult()
            .getFieldErrors()
            .stream()
            .map(f -> new ApiError.FieldError(f.getField(), f.getDefaultMessage()))
            .toList();

    ApiError error = new ApiError(
            ApiErrorCode.VALIDATION_FAILED,
            "Validation error",
            fields
    );

    return ResponseEntity.badRequest().body(error);
  }

  @ExceptionHandler(Exception.class)
  public ResponseEntity<ApiError> handleUnexpected(
          Exception ex
  ) {
    log.error("Unhandled exception", ex);
    ApiError error = new ApiError(
            ApiErrorCode.INTERNAL_ERROR,
            "Unexpected server error",
            null
    );
    return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body(error);
  }
}
