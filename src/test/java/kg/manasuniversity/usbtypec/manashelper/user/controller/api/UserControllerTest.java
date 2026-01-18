package kg.manasuniversity.usbtypec.manashelper.user.controller.api;

import com.fasterxml.jackson.databind.ObjectMapper;
import kg.manasuniversity.usbtypec.manashelper.user.dto.request.UserUpdateCredentialsRequest;
import kg.manasuniversity.usbtypec.manashelper.user.dto.request.UserUpsertRequest;
import kg.manasuniversity.usbtypec.manashelper.user.dto.response.UsersStatisticsResponse;
import kg.manasuniversity.usbtypec.manashelper.user.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.user.service.UserService;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.AutoConfigureMockMvc;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

@WebMvcTest(UserController.class)
@AutoConfigureMockMvc(addFilters = false)
class UserControllerTest {

  @Autowired
  MockMvc mockMvc;

  @MockitoBean
  UserService userService;

  @Test
  void upsertUser_shouldReturn204_andCallService() throws Exception {
    ObjectMapper objectMapper = new ObjectMapper();
    UserUpsertRequest req = new UserUpsertRequest(
            123L,
            "Eldos Baktybek uulu",
            "eldos"
    );

    mockMvc.perform(post("/api/users")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(objectMapper.writeValueAsString(req)))
            .andExpect(status().isNoContent())
            .andExpect(content().string(""));

    ArgumentCaptor<UserUpsertRequest> captor = ArgumentCaptor.forClass(UserUpsertRequest.class);
    verify(userService).upsertUser(captor.capture());
    assertEquals(123L, captor.getValue().id());
    assertEquals("Eldos Baktybek uulu", captor.getValue().fullName());
    assertEquals("eldos", captor.getValue().username());

    verifyNoMoreInteractions(userService);
  }

  @Test
  void updateUserCredentials_shouldReturn204_andCallServiceWithPathId() throws Exception {
    ObjectMapper objectMapper = new ObjectMapper();

    long userId = 555L;
    UserUpdateCredentialsRequest req = new UserUpdateCredentialsRequest(
            "20201234",
            "plainPassword123"
    );

    mockMvc.perform(put("/api/users/{id}/credentials", userId)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(objectMapper.writeValueAsString(req)))
            .andExpect(status().isNoContent())
            .andExpect(content().string(""));

    ArgumentCaptor<UserUpdateCredentialsRequest> captor = ArgumentCaptor.forClass(UserUpdateCredentialsRequest.class);
    verify(userService).updateUserCredentials(eq(userId), captor.capture());
    assertEquals("20201234", captor.getValue().studentNumber());
    assertEquals("plainPassword123", captor.getValue().plainPassword());

    verifyNoMoreInteractions(userService);
  }

  @Test
  void getUserStatistics_shouldReturn200_andJson() throws Exception {
    when(userService.getUsersStatistics()).thenReturn(new UsersStatisticsResponse(10, 4));

    mockMvc.perform(get("/api/users/statistics"))
            .andExpect(status().isOk())
            .andExpect(content().contentType(MediaType.APPLICATION_JSON))
            .andExpect(jsonPath("$.totalUsersCount").value(10))
            .andExpect(jsonPath("$.usersWithCredentialsCount").value(4));

    verify(userService).getUsersStatistics();
    verifyNoMoreInteractions(userService);
  }

  @Test
  void updateUserCredentials_shouldReturn404_whenServiceThrowsUserNotFound() throws Exception {
    long userId = 999L;
    ObjectMapper objectMapper = new ObjectMapper();

    UserUpdateCredentialsRequest req = new UserUpdateCredentialsRequest("20209999", "pw");

    doThrow(new UserNotFoundException("User not found with id: " + userId))
            .when(userService).updateUserCredentials(eq(userId), any(UserUpdateCredentialsRequest.class));

    mockMvc.perform(put("/api/users/{id}/credentials", userId)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(objectMapper.writeValueAsString(req)))
            .andExpect(status().isNotFound());

    verify(userService).updateUserCredentials(eq(userId), any(UserUpdateCredentialsRequest.class));
    verifyNoMoreInteractions(userService);
  }

  @Test
  void upsertUser_shouldReturn400_whenInvalidBody() throws Exception {
    String invalidJson = """
            {
              "id": 0,
              "fullName": "",
              "username": ""
            }
            """;

    mockMvc.perform(post("/api/users")
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(invalidJson))
            .andExpect(status().isBadRequest());

    verifyNoInteractions(userService);
  }

  @Test
  void updateUserCredentials_shouldReturn400_whenInvalidBody() throws Exception {
    String invalidJson = """
            {
              "studentNumber": "",
              "plainPassword": ""
            }
            """;

    mockMvc.perform(put("/api/users/{id}/credentials", 1L)
                    .contentType(MediaType.APPLICATION_JSON)
                    .content(invalidJson))
            .andExpect(status().isBadRequest());

    verifyNoInteractions(userService);
  }
}
