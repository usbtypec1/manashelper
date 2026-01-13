package kg.manasuniversity.usbtypec.manashelper.mapper;

import kg.manasuniversity.usbtypec.manashelper.model.Lesson;
import org.springframework.stereotype.Component;

@Component
public class LessonMapper {
  public Lesson mapEntityToLesson(kg.manasuniversity.usbtypec.manashelper.entity.Lesson lessonEntity) {
    return new Lesson(
            lessonEntity.getCourse().getId(),
            lessonEntity.getName(),
            lessonEntity.getTeacherName(),
            lessonEntity.getLocation(),
            lessonEntity.getType(),
            lessonEntity.getWeekday()
    );
  }
}
