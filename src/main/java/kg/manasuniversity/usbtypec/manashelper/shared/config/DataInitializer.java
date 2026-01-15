package kg.manasuniversity.usbtypec.manashelper.shared.config;

import jakarta.transaction.Transactional;
import kg.manasuniversity.usbtypec.manashelper.timetable.service.TimetableDataLoadService;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
@Transactional
public class DataInitializer implements CommandLineRunner {
  private final TimetableDataLoadService timetableDataLoadService;

  public DataInitializer(TimetableDataLoadService timetableDataLoadService) {
    this.timetableDataLoadService = timetableDataLoadService;
  }

  @Override
  public void run(String... args) throws Exception {
    timetableDataLoadService.loadInitialTimetableData();
  }
}
