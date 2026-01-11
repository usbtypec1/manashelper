package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

@Entity
@Table(name = "courses")
public class Course {
  @Id
  private Integer id;

  @Column(name = "number", nullable = false)
  private Integer number;

  @ManyToOne(fetch = FetchType.LAZY)
  @JoinColumn(name = "department_id", nullable = false)
  private Department department;

  protected Course() {
  }

  public Course(Integer id, Integer number, Department department) {
    this.id = id;
    this.number = number;
    this.department = department;
  }

  public Integer getId() {
    return id;
  }

  public Integer getNumber() {
    return number;
  }
}
