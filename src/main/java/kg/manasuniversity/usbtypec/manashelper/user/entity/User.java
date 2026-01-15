package kg.manasuniversity.usbtypec.manashelper.user.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.Table;
import kg.manasuniversity.usbtypec.manashelper.timetable.entity.Course;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(name = "users")
public class User {
  @Id
  private Long id;

  @Column(name = "full_name", nullable = false, length = 128)
  private String fullName;

  @Column(name = "username", nullable = true, length = 128)
  private String username;

  @Column(name = "student_number", nullable = true, length = 64)
  private String studentNumber;

  @Column(name = "encrypted_password", nullable = true)
  private String encryptedPassword;

  @ManyToMany
  @JoinTable(
          name = "user_courses",
          joinColumns = @JoinColumn(name = "user_id"),
          inverseJoinColumns = @JoinColumn(name = "course_id")
  )
  private Set<Course> courses;

  @CreatedDate
  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;

  @LastModifiedDate
  @Column(name = "updated_at", nullable = false)
  private LocalDateTime updatedAt;

  protected User() {
    courses = new HashSet<>();
  }

  public User(Long id, String fullName, String username) {
    this.id = id;
    this.fullName = fullName;
    this.username = username;
    courses = new HashSet<>();
  }

  public Long getId() {
    return id;
  }

  public String getStudentNumber() {
    return studentNumber;
  }

  public String getEncryptedPassword() {
    return encryptedPassword;
  }

  public void setStudentNumber(String studentNumber) {
    this.studentNumber = studentNumber;
  }

  public void setEncryptedPassword(String encryptedPassword) {
    this.encryptedPassword = encryptedPassword;
  }

  public void setCourses(List<Course> courses) {
    if (courses.size() > 5) {
      throw new IllegalArgumentException("A user cannot be enrolled in more than 5 courses.");
    } else {
      clearCourses();
      this.courses.addAll(courses);
    }
  }

  public String getFullName() {
    return fullName;
  }

  public void clearCourses() {
    courses.clear();
  }

  public Set<Course> getCourses() {
    return courses;
  }

  public void setFullName(String fullName) {
    this.fullName = fullName;
  }

  public void setUsername(String username) {
    this.username = username;
  }
}
