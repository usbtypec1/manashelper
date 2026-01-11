package kg.manasuniversity.usbtypec.manashelper.scheduledtasks;

import kg.manasuniversity.usbtypec.manashelper.service.LessonSynchronizeService;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class SynchronizeLessonsTask {
  private final LessonSynchronizeService lessonSynchronizeService;

  public SynchronizeLessonsTask(LessonSynchronizeService lessonSynchronizeService) {
    this.lessonSynchronizeService = lessonSynchronizeService;
  }

  @Scheduled(cron = "0 0 * * * *")
  public void synchronizeLessons() {
    lessonSynchronizeService.synchronizeLessons();
  }
}
