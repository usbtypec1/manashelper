package kg.manasuniversity.usbtypec.manashelper.user.mapper;

import kg.manasuniversity.usbtypec.manashelper.user.dto.response.LessonAttendanceResponse;
import kg.manasuniversity.usbtypec.manashelper.user.integration.obis.model.LessonAttendance;
import org.springframework.stereotype.Service;

@Service
public class LessonAttendanceMapper {
  public LessonAttendanceResponse mapToResponse(LessonAttendance lessonAttendance) {
    return new LessonAttendanceResponse(
            lessonAttendance.lessonName(),
            lessonAttendance.lessonCode(),
            lessonAttendance.theorySkipsPercentage(),
            lessonAttendance.practiceSkipsPercentage()
    );
  }
}
