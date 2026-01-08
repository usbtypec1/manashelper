package kg.manasuniversity.usbtypec.manashelper.controller.api;

import jakarta.validation.Valid;
import kg.manasuniversity.usbtypec.manashelper.payload.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.service.UserService;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
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
    try {
      userService.upsertUser(userRequest);
      return ResponseEntity.ok().build();
    } catch (Exception e) {
      e.printStackTrace();
      return ResponseEntity.internalServerError().build();
    }
  }
}
