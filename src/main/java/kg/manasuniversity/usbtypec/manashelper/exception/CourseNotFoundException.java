package kg.manasuniversity.usbtypec.manashelper.exception;

import java.util.List;

public class CourseNotFoundException extends RuntimeException {
  private final List<Integer> missingCourseIds;

  public CourseNotFoundException(List<Integer> missingCourseIds) {
    super("Courses not found for IDs: " + missingCourseIds);
    this.missingCourseIds = missingCourseIds;
  }

  public List<Integer> getMissingCourseIds() {
    return missingCourseIds;
  }
}
