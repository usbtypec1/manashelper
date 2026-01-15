package kg.manasuniversity.usbtypec.manashelper.telegram.repository;

import kg.manasuniversity.usbtypec.manashelper.telegram.entity.TelegramMessage;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface TelegramMessageRepository extends JpaRepository<TelegramMessage, Long> {
  List<TelegramMessage> findBySentAtNullAndRetriesCountGreaterThanOrderByPriorityDesc(Integer retriesCount);
}
