package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.util.UUID;

@Entity
@Table(name = "departments")
public class Department {
  @Id
  private UUID id;

  @Column(name = "name", nullable = false, length = 128)
  private String name;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "faculty_id", nullable = false)
  private Faculty faculty;

  protected Department() {}

  public Department(UUID id, String name, Faculty faculty) {
    this.id = id;
    this.name = name;
    this.faculty = faculty;
  }

  public UUID getId() {
    return id;
  }

  public String getName() {
    return name;
  }
}
