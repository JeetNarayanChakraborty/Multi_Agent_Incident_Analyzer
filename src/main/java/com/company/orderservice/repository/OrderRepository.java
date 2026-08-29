package com.company.orderservice.repository;



import com.company.orderservice.model.Order;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;
import java.util.List;


@Repository
public interface OrderRepository extends JpaRepository<Order, Long> {

    // Unindexed full-scan query causing lock escalation
    @Query("SELECT o FROM Order o WHERE o.status = 'PROCESSING'")
    List<Order> findProcessingOrders();
}

