package kg.manasuniversity.usbtypec.manashelper.telegram.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(name = "telegram_messages")
@Getter
@Setter
@NoArgsConstructor
public class TelegramMessage {
  @Id
  @GeneratedValue(strategy = GenerationType.SEQUENCE)
  private Long id;

  @Column(name = "text", nullable = false, length = 1024)
  private String text;

  @Column(name = "chat_id", nullable = false)
  private Long chatId;

  @Column(name = "sent_message_id")
  private Long sentMessageId;

  @Column(name = "sent_at")
  private LocalDateTime sentAt;

  @Column(name = "error_text", length = 1024)
  private String errorText;

  @Column(name = "retries_count", nullable = false)
  private Integer retriesCount;

  @Column(name = "priority", nullable = false)
  private Integer priority;

  @CreatedDate
  @Column(name = "created_at", nullable = false, updatable = false, columnDefinition = "timestamp default now()")
  private LocalDateTime createdAt;

  public TelegramMessage(String text, Long chatId) {
    this.text = text;
    this.chatId = chatId;
    retriesCount = 3;
    priority = 0;
  }
}
