package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.Course;
import kg.manasuniversity.usbtypec.manashelper.entity.User;
import kg.manasuniversity.usbtypec.manashelper.exception.CourseNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.exception.UserNotFoundException;
import kg.manasuniversity.usbtypec.manashelper.model.CourseSummary;
import kg.manasuniversity.usbtypec.manashelper.repository.CourseRepository;
import kg.manasuniversity.usbtypec.manashelper.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Set;
import java.util.UUID;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class CourseService {
    private final CourseRepository courseRepository;
    private final UserRepository userRepository;

    public List<CourseSummary> getCoursesByDepartment(UUID departmentId, Long userId) {
        List<Course> courses = courseRepository.findAllByDepartmentId(departmentId);
        Set<Integer> trackedCourseIds = getTrackedCourseIds(userId);
        return toSummaries(courses, trackedCourseIds);
    }

    @Transactional
    public List<CourseSummary> toggleTrackedCourse(int courseId, Long userId) {
        Course course = courseRepository.findById(courseId)
            .orElseThrow(() -> new CourseNotFoundException("Course not found with id: " + courseId));
        User user = userRepository.findByIdWithCourses(userId)
            .orElseThrow(() -> new UserNotFoundException("User not found with id: " + userId));

        if (user.getCourses().contains(course)) {
            user.removeCourse(course);
        } else {
            user.addCourse(course);
        }
        userRepository.save(user);

        List<Course> siblingCourses = courseRepository.findAllByDepartmentId(course.getDepartment().getId());
        Set<Integer> trackedCourseIds = user.getCourses().stream().map(Course::getId).collect(Collectors.toSet());
        return toSummaries(siblingCourses, trackedCourseIds);
    }

    private Set<Integer> getTrackedCourseIds(Long userId) {
        return userRepository.findByIdWithCourses(userId)
            .map(user -> user.getCourses().stream().map(Course::getId).collect(Collectors.toSet()))
            .orElseGet(Set::of);
    }

    private List<CourseSummary> toSummaries(List<Course> courses, Set<Integer> trackedCourseIds) {
        return courses.stream()
            .map(course -> new CourseSummary(
                course.getId(),
                course.getNumber(),
                trackedCourseIds.contains(course.getId())
            ))
            .toList();
    }
}
