package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.time.LocalDateTime;

@Entity
@EntityListeners(AuditingEntityListener.class)
@Table(name = "users")
public class User {
  @Id
  private Long id;

  @Column(name = "student_number", nullable = true, length = 64)
  private String studentNumber;

  @Column(name = "encrypted_password", nullable = true)
  private String encryptedPassword;

  @CreatedDate
  @Column(name = "created_at", nullable = false, updatable = false)
  private LocalDateTime createdAt;

  @LastModifiedDate
  @Column(name = "updated_at", nullable = false)
  private LocalDateTime updatedAt;

  protected User() {}

  public User(Long id, String studentNumber, String encryptedPassword) {
    this.id = id;
    this.studentNumber = studentNumber;
    this.encryptedPassword = encryptedPassword;
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

  public LocalDateTime getCreatedAt() {
    return createdAt;
  }

  public LocalDateTime getUpdatedAt() {
    return updatedAt;
  }

  public void setStudentNumber(String studentNumber) {
    this.studentNumber = studentNumber;
  }

  public void setEncryptedPassword(String encryptedPassword) {
    this.encryptedPassword = encryptedPassword;
  }
}
