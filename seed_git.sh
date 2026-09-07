#!/bin/bash
set -e



# Initialize git repository
git init -b main
git config user.name "release-bot"
git config user.email "bot@company.internal"

echo "# Order Service" > README.md
git add README.md
git commit -m "chore: initial repository setup"

# Realistic Spring Boot file structure
mkdir -p src/main/java/com/company/orderservice/{controller,service,repository,model,config}



# 1. Generate 85 realistic standard development commits

modules=("controller" "service" "config" "model")

for i in $(seq 1 85); do
    mod=${modules[$((RANDOM % ${#modules[@]}))]}
    file="src/main/java/com/company/orderservice/${mod}/Component_${i}.java"

    cat <<EOF > "$file"

package com.company.orderservice.${mod};

public class Component_${i} {

    // Routine update cycle $i
    private String status = "HEALTHY";

}

EOF

    git add "$file"
    git commit -m "feat(${mod}): routine refactor iteration ${i}"

done

# 2. Add the Spring Data JPA Domain Entity

cat <<EOF > src/main/java/com/company/orderservice/model/Order.java

package com.company.orderservice.model;



import jakarta.persistence.*;



@Entity
@Table(name = "orders")
public class Order {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String status;
}

EOF

git add src/main/java/com/company/orderservice/model/Order.java
git commit -m "feat(domain): define Order entity mapping"



# 3. Add the target Spring Data JPA Repository (The Root Cause PR)

cat <<EOF > src/main/java/com/company/orderservice/repository/OrderRepository.java
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

EOF

git add src/main/java/com/company/orderservice/repository/OrderRepository.java
git commit -m "feat(repo): add findProcessingOrders method in OrderRepository"


# Push all commits to remote
git remote add origin "https://github.com/${GITHUB_REPO}.git" || true
git push -u origin main --force