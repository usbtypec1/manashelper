package kg.manasuniversity.usbtypec.manashelper.user.controller.api;

import jakarta.validation.Valid;
import kg.manasuniversity.usbtypec.manashelper.user.dto.request.UserUpdateCredentialsRequest;
import kg.manasuniversity.usbtypec.manashelper.user.dto.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.user.dto.response.UsersStatisticsResponse;
import kg.manasuniversity.usbtypec.manashelper.user.service.UserService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/users")
public class UserController {
  private final UserService userService;

  public UserController(UserService userService) {
    this.userService = userService;
  }

  @PostMapping
  public ResponseEntity<Void> upsertUser(
          @Valid @RequestBody UserUpsertRequest userRequest
  ) {
    userService.upsertUser(userRequest);
    return ResponseEntity.noContent().build();
  }

  @PutMapping("/{id}/credentials")
  public ResponseEntity<Void> updateUserCredentials(
          @PathVariable long id,
          @Valid @RequestBody UserUpdateCredentialsRequest userRequest
  ) {
    userService.updateUserCredentials(id, userRequest);
    return ResponseEntity.noContent().build();
  }

  @GetMapping("/statistics")
  public ResponseEntity<UsersStatisticsResponse> getUserStatistics() {
    UsersStatisticsResponse statistics = userService.getUsersStatistics();
    return ResponseEntity.ok(statistics);
  }
}
