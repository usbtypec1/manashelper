package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

import java.util.UUID;

@Entity
@Table(name = "faculties")
public class Faculty {
  @Id
  private UUID id;

  @Column(name = "name", nullable = false, length = 128)
  private String name;

  protected Faculty() {
  }

  public Faculty(UUID id, String name) {
    this.id = id;
    this.name = name;
  }
}
