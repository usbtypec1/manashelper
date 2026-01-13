package kg.manasuniversity.usbtypec.manashelper.service.timetable;

import kg.manasuniversity.usbtypec.manashelper.entity.TelegramMessage;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.model.CourseLesson;
import kg.manasuniversity.usbtypec.manashelper.model.TimetableLessonChanges;
import kg.manasuniversity.usbtypec.manashelper.repository.TelegramMessageRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
public class LessonNotificationService {
  private final UserRepository userRepository;
  private final TelegramMessageRepository telegramMessageRepository;
  private final CourseLessonFormatter courseLessonFormatter;

  public LessonNotificationService(
          UserRepository userRepository,
          TelegramMessageRepository telegramMessageRepository,
          CourseLessonFormatter courseLessonFormatter) {
    this.userRepository = userRepository;
    this.telegramMessageRepository = telegramMessageRepository;
    this.courseLessonFormatter = courseLessonFormatter;
  }

  public void notifyUsersOfChanges(TimetableLessonChanges changes) {
    notifyUsersOfLessonChanges(changes.addedLessons(), courseLessonFormatter::formatAddedLesson);
    notifyUsersOfLessonChanges(changes.removedLessons(), courseLessonFormatter::formatRemovedLesson);
  }

  private void notifyUsersOfLessonChanges(
          List<CourseLesson> lessons,
          Function<CourseLesson, String> messageFormatter) {
    lessons.forEach(lesson -> {
      List<User> users = userRepository.findByCourses_Id(lesson.courseId());
      List<TelegramMessage> messages = createMessagesForUsers(users, lesson, messageFormatter);
      telegramMessageRepository.saveAll(messages);
    });
  }

  private List<TelegramMessage> createMessagesForUsers(
          List<User> users,
          CourseLesson lesson,
          Function<CourseLesson, String> messageFormatter) {
    String messageText = messageFormatter.apply(lesson);
    return users.stream()
            .map(user -> new TelegramMessage(messageText, user.getId()))
            .collect(Collectors.toList());
  }
}