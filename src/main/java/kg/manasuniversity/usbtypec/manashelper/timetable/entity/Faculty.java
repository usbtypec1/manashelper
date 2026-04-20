package kg.manasuniversity.usbtypec.manashelper.timetable.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Entity
@Table(name = "faculties")
@Getter
@NoArgsConstructor
@AllArgsConstructor
public class Faculty {
    @Id
    private UUID id;

    @Column(name = "name", nullable = false, length = 128)
    private String name;
}
