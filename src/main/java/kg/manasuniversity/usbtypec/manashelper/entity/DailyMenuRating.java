package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(name = "daily_menu_ratings")
public class DailyMenuRating {
  @Id
  @GeneratedValue(strategy = jakarta.persistence.GenerationType.UUID)
  private UUID id;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "daily_menu_id", nullable = false)
  private DailyMenu dailyMenu;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "user_id", nullable = false)
  private User user;

  @Column(name = "score", nullable = false)
  @Min(1)
  @Max(5)
  private Integer score;

  @Column(name = "comment", length = 255)
  private String comment;

  @CreatedDate
  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;

  protected DailyMenuRating() {
  }

  public DailyMenuRating(DailyMenu dailyMenu, User user, Integer score, String comment) {
    this.dailyMenu = dailyMenu;
    this.user = user;
    this.score = score;
    this.comment = comment;
  }
}
