package kg.manasuniversity.usbtypec.manashelper.controller.api;

import kg.manasuniversity.usbtypec.manashelper.service.timetable.LessonSynchronizeService;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping
public class SynchronizeController {
  private final LessonSynchronizeService lessonSynchronizeService;

  public SynchronizeController(LessonSynchronizeService lessonSynchronizeService) {
    this.lessonSynchronizeService = lessonSynchronizeService;
  }

  @PostMapping("/api/synchronize-lessons")
  public void synchronizeLessons() {
    lessonSynchronizeService.synchronizeLessons();
  }
}
