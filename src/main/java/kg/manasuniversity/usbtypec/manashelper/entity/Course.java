package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;

import java.util.HashSet;
import java.util.Set;

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

  @ManyToMany(mappedBy = "courses")
  private Set<User> users;

  protected Course() {
    users = new HashSet<>();
  }

  public Course(Integer id, Integer number, Department department) {
    this.id = id;
    this.number = number;
    this.department = department;
    users = new HashSet<>();
  }

  public Integer getId() {
    return id;
  }

  public Integer getNumber() {
    return number;
  }

  public Department getDepartment() {
    return department;
  }
}
