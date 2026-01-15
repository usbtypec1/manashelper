package kg.manasuniversity.usbtypec.manashelper.timetable.scheduler;

import kg.manasuniversity.usbtypec.manashelper.timetable.service.LessonSynchronizeService;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class SynchronizeLessonsJob {
  private final LessonSynchronizeService lessonSynchronizeService;

  public SynchronizeLessonsJob(LessonSynchronizeService lessonSynchronizeService) {
    this.lessonSynchronizeService = lessonSynchronizeService;
  }

  @Scheduled(cron = "0 0 * * * *")
  public void synchronizeLessons() {
    lessonSynchronizeService.synchronizeLessons();
  }
}
