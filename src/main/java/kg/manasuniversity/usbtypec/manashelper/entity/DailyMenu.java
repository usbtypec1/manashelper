package kg.manasuniversity.usbtypec.manashelper.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.JoinTable;
import jakarta.persistence.ManyToMany;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;

import java.time.LocalDate;
import java.util.LinkedHashSet;
import java.util.Set;
import java.util.UUID;

@Entity
@Table(name = "daily_menus")
public class DailyMenu {
  @Id
  @GeneratedValue(strategy = jakarta.persistence.GenerationType.UUID)
  private UUID id;

  @Column(name = "date", nullable = false)
  private LocalDate date;

  @ManyToMany(fetch = FetchType.LAZY)
  @JoinTable(
          name = "daily_menu_dishes",
          joinColumns = @JoinColumn(name = "menu_id", nullable = false),
          inverseJoinColumns = @JoinColumn(name = "dish_id", nullable = false),
          uniqueConstraints = {
                  @UniqueConstraint(name = "uk_daily_menu_dishes_menu_dish", columnNames = {"menu_id", "dish_id"})
          }
  )
  private Set<Dish> dishes;

  protected DailyMenu() {
  }

  public DailyMenu(LocalDate date) {
    this.date = date;
    dishes = new LinkedHashSet<>();
  }

  public Set<Dish> getDishes() {
    return dishes;
  }

  public void addDish(Dish dish) {
    dishes.add(dish);
  }

  public void clearDishes() {
    dishes.clear();
  }

  public UUID getId() {
    return id;
  }

  public void setDishes(Set<Dish> dishes) {
    this.dishes.clear();
    this.dishes.addAll(dishes);
  }

}
