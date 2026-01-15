package kg.manasuniversity.usbtypec.manashelper.telegram.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(name = "telegram_messages")
public class TelegramMessage {
  @Id
  @GeneratedValue(strategy = GenerationType.SEQUENCE)
  private Long id;

  @Column(name = "text", nullable = false, length = 1024)
  private String text;

  @Column(name = "chat_id", nullable = false)
  private Long chatId;

  @Column(name = "sent_message_id", nullable = true)
  private Long sentMessageId;

  @Column(name = "sent_at", nullable = true)
  private LocalDateTime sentAt;

  @Column(name = "error_text", nullable = true, length = 1024)
  private String errorText;

  @Column(name = "retries_count", nullable = false)
  private Integer retriesCount;

  @Column(name = "priority", nullable = false)
  private Integer priority;

  @CreatedDate
  @Column(name = "created_at", nullable = false, updatable = false, columnDefinition = "timestamp default now()")
  private LocalDateTime createdAt;

  protected TelegramMessage() {}

  public TelegramMessage(String text, Long chatId) {
    this.text = text;
    this.chatId = chatId;
    retriesCount = 3;
    priority = 0;
  }

  public void setSentAt(LocalDateTime sentAt) {
    this.sentAt = sentAt;
  }

  public void setRetriesCount(Integer retriesCount) {
    this.retriesCount = retriesCount;
  }

  public void setErrorText(String errorText) {
    this.errorText = errorText;
  }

  public Integer getRetriesCount() {
    return retriesCount;
  }

  public Long getChatId() {
    return chatId;
  }

  public String getText() {
    return text;
  }
}
