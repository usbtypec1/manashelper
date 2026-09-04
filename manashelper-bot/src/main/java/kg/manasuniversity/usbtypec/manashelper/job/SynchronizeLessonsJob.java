package kg.manasuniversity.usbtypec.manashelper.job;

import kg.manasuniversity.usbtypec.manashelper.service.LessonSynchronizeService;
import lombok.RequiredArgsConstructor;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@RequiredArgsConstructor
public class SynchronizeLessonsJob {
    private final LessonSynchronizeService lessonSynchronizeService;

    @Scheduled(cron = "0 0 * * * *")
    public void synchronizeLessons() {
        lessonSynchronizeService.synchronizeLessons();
    }
}
