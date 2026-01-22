package kg.manasuniversity.usbtypec.manashelper.shared.exception;

import kg.manasuniversity.usbtypec.manashelper.foodmenu.dailymenu.exception.DailyMenuNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.foodmenu.rating.dailymenu.exception.DailyMenuRatingNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.ObisLoginException;
import kg.manasuniversity.usbtypec.manashelper.timetable.exception.CourseNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.timetable.exception.DepartmentNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.timetable.exception.FacultyNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserHasNoCredentialsException;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserNotFoundException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.MissingServletRequestParameterException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.List;

@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {
  @ExceptionHandler(DailyMenuRatingNotFoundException.class)
  public ResponseEntity<ApiError> handleDailyMenuRatingNotFound(
          DailyMenuRatingNotFoundException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.DAILY_MENU_RATING_NOT_FOUND,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
  }

  @ExceptionHandler(DailyMenuNotFoundException.class)
  public ResponseEntity<ApiError> handleDailyMenuNotFound(
          DailyMenuNotFoundException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.DAILY_MENU_NOT_FOUND,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.NOT_FOUND).body(apiError);
  }

  @ExceptionHandler(ObisLoginException.class)
  public ResponseEntity<ApiError> handleObisLoginException(
          ObisLoginException ex
  ) {
    ApiError apiError = new ApiError(
            ApiErrorCode.OBIS_LOGIN_FAILED,
            ex.getMessage(),
            null
    );
    return ResponseEntity.status(HttpStatus.UNAUTHORIZED).body(apiError);
  }

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

  @ExceptionHandler(MissingServletRequestParameterException.class)
  public ResponseEntity<ApiError> handleMissingRequestParam(
          MissingServletRequestParameterException ex
  ) {
    ApiError error = new ApiError(
            ApiErrorCode.VALIDATION_FAILED,
            ex.getMessage(),
            List.of(new ApiError.FieldError(ex.getParameterName(), "Required parameter is missing"))
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
