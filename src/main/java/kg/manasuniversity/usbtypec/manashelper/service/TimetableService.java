package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.exception.CourseNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.mapper.TimetableMapper;
import kg.manasuniversity.usbtypec.manashelper.payload.response.UserTrackingCourseResponse;
import kg.manasuniversity.usbtypec.manashelper.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import org.springframework.stereotype.Service;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Service
public class TimetableService {
  private final UserRepository userRepository;
  private final CourseRepository courseRepository;
  private final TimetableMapper timetableMapper;

  public TimetableService(UserRepository userRepository, CourseRepository courseRepository, TimetableMapper timetableMapper) {
    this.userRepository = userRepository;
    this.courseRepository = courseRepository;
    this.timetableMapper = timetableMapper;
  }

  private void validateCoursesExistence(List<Integer> courseIds) throws CourseNotFoundException {
    List<Course> courses = courseRepository.findAllById(courseIds);
    Set<Integer> courseIdsToCheck = new HashSet<>(courseIds);
    for (Course course : courses) {
      courseIdsToCheck.remove(course.getId());
    }
    if (!courseIdsToCheck.isEmpty()) {
      throw new CourseNotFoundException("Courses not found with ids: " + new ArrayList<>(courseIdsToCheck));
    }
  }

  public void updateUserTrackingCourses(long userId, List<Integer> courseIds)
          throws CourseNotFoundException, UserNotFoundException {
    User user = userRepository
            .findById(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));
    if (courseIds.isEmpty()) {
      user.clearCourses();
    } else {
      List<Course> courses = courseRepository.findAllById(courseIds);
      validateCoursesExistence(courseIds);
      user.setCourses(courses);
    }
    userRepository.save(user);
  }

  public UserTrackingCourseResponse getUserTrackingCourses(long userId) throws UserNotFoundException {
    User user = userRepository
            .findByIdWithCoursesAndDepartments(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));
    List<UserTrackingCourseResponse.Course> courses = user
            .getCourses()
            .stream()
            .map(timetableMapper::mapToUserTrackingCourseResponseCourse)
            .toList();
    return new UserTrackingCourseResponse(userId, courses);
  }
}
