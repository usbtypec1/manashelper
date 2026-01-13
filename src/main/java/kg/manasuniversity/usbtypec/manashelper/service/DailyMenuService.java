package kg.manasuniversity.usbtypec.manashelper.service;

import kg.manasuniversity.usbtypec.manashelper.entity.DailyMenu;
import kg.manasuniversity.usbtypec.manashelper.mapper.DailyMenuMapper;
import kg.manasuniversity.usbtypec.manashelper.repository.DailyMenuRepository;
import org.springframework.stereotype.Service;

import java.util.List;

@Service
public class DailyMenuService {
  private final DailyMenuRepository dailyMenuRepository;
  private final DailyMenuMapper dailyMenuMapper;

  public DailyMenuService(DailyMenuRepository dailyMenuRepository, DailyMenuMapper dailyMenuMapper) {
    this.dailyMenuRepository = dailyMenuRepository;
    this.dailyMenuMapper = dailyMenuMapper;
  }

  public List<kg.manasuniversity.usbtypec.manashelper.model.DailyMenu> getLastDailyMenus() {
    List<DailyMenu> dailyMenus = dailyMenuRepository.findTop30ByOrderByDateAsc();
    return dailyMenus.stream().map(dailyMenuMapper::mapEntityToModel).toList();
  }
}
