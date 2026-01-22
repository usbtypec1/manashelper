package kg.manasuniversity.usbtypec.manashelper.foodmenu.dish.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;
import java.util.UUID;

@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(
        name = "dishes",
        indexes = {
                @Index(name = "ix_dishes_name", columnList = "name")
        }
)
@Getter
@NoArgsConstructor
public class Dish {
  @Id
  @GeneratedValue(strategy = GenerationType.UUID)
  private UUID id;

  @Column(name = "name", unique = true, nullable = false)
  private String name;

  @Column(name = "photo_url", nullable = false)
  private String photoUrl;

  @Column(name = "calories", nullable = false)
  private Integer calories;

  @Column(name = "upscaled_photo_url")
  private String upscaledPhotoUrl;

  @CreatedDate
  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;

  public Dish(String name, String photoUrl, Integer calories) {
    this.name = name;
    this.photoUrl = photoUrl;
    this.calories = calories;
  }
}
