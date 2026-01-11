package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import kg.manasuniversity.usbtypec.manashelper.enums.LessonType;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.UUID;

@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(
        name = "lessons",
        indexes = {
                @Index(name = "idx_lessons_course_id", columnList = "course_id"),
                @Index(name = "idx_lessons_time", columnList = "starts_at, ends_at")
        }
)
public class Lesson {
  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @Column(name = "synchronization_id", nullable = false, updatable = false)
  private UUID synchronizationId;

  @Column(name = "name", nullable = false, length = 128)
  private String name;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "course_id", nullable = false)
  private Course course;

  @Column(name = "teacher_name", nullable = false, length = 128)
  private String teacherName;

  @Column(name = "location", nullable = false, length = 128)
  private String location;

  @Column(name = "starts_at", nullable = false)
  private LocalTime startsAt;

  @Column(name = "ends_at", nullable = false)
  private LocalTime endsAt;

  @Column(name = "weekday", nullable = false)
  private Integer weekday;

  @Enumerated(EnumType.STRING)
  @Column(name = "type", nullable = false)
  private LessonType type;

  @CreatedDate
  @Column(name = "created_at", nullable = false, updatable = false, columnDefinition = "timestamp default now()")
  private LocalDateTime createdAt;

  protected Lesson() {
  }

  public Lesson(UUID synchronizationId, String name, Course course, String teacherName, String location, LocalTime startsAt, LocalTime endsAt, int weekday, LessonType type) {
    this.synchronizationId = synchronizationId;
    this.name = name;
    this.course = course;
    this.teacherName = teacherName;
    this.location = location;
    this.startsAt = startsAt;
    this.endsAt = endsAt;
    this.weekday = weekday;
    this.type = type;
  }

  public UUID getId() {
    return id;
  }

  public String getName() {
    return name;
  }

  public Course getCourse() {
    return course;
  }

  public String getTeacherName() {
    return teacherName;
  }

  public String getLocation() {
    return location;
  }

  public LocalTime getStartsAt() {
    return startsAt;
  }

  public LocalTime getEndsAt() {
    return endsAt;
  }

  public Integer getWeekday() {
    return weekday;
  }

  public LessonType getType() {
    return type;
  }

  public LocalDateTime getCreatedAt() {
    return createdAt;
  }

  public UUID getSynchronizationId() {
    return synchronizationId;
  }
}
