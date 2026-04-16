-- MySQL dump 10.13  Distrib 8.0.43, for Win64 (x86_64)
--
-- Host: cpsc4910-s26.cobd8enwsupz.us-east-1.rds.amazonaws.com    Database: Team16_DB
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;
SET @MYSQLDUMP_TEMP_LOG_BIN = @@SESSION.SQL_LOG_BIN;
SET @@SESSION.SQL_LOG_BIN= 0;

--
-- GTID state at the beginning of the backup 
--

SET @@GLOBAL.GTID_PURGED=/*!80000 '+'*/ '';

--
-- Table structure for table `about_page`
--

DROP TABLE IF EXISTS `about_page`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `about_page` (
  `team_num` int NOT NULL,
  `sprint_num` int NOT NULL,
  `release_date` datetime NOT NULL,
  `product_name` varchar(255) NOT NULL,
  `product_description` varchar(255) NOT NULL,
  `last_update` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`team_num`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Temporary view structure for view `audit_log`
--

DROP TABLE IF EXISTS `audit_log`;
/*!50001 DROP VIEW IF EXISTS `audit_log`*/;
SET @saved_cs_client     = @@character_set_client;
/*!50503 SET character_set_client = utf8mb4 */;
/*!50001 CREATE VIEW `audit_log` AS SELECT 
 1 AS `user_id`,
 1 AS `username`,
 1 AS `role_type`,
 1 AS `event_type`,
 1 AS `detail`,
 1 AS `event_time`,
 1 AS `organization_id`,
 1 AS `organization_status`*/;
SET character_set_client = @saved_cs_client;

--
-- Table structure for table `driver_applications`
--

DROP TABLE IF EXISTS `driver_applications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_applications` (
  `application_id` int NOT NULL AUTO_INCREMENT,
  `driver_id` int NOT NULL,
  `organization_id` int NOT NULL,
  `status` enum('PENDING','APPROVED','REJECTED') NOT NULL DEFAULT 'PENDING',
  `reason` text,
  `decision_date` datetime DEFAULT NULL,
  `decided_by_user_id` int DEFAULT NULL,
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `full_name` varchar(255) DEFAULT NULL,
  `phone_number` varchar(50) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `experience` text,
  PRIMARY KEY (`application_id`),
  KEY `driver_id` (`driver_id`),
  KEY `organization_id` (`organization_id`),
  KEY `decided_by_user_id` (`decided_by_user_id`),
  CONSTRAINT `driver_applications_ibfk_1` FOREIGN KEY (`driver_id`) REFERENCES `drivers` (`driver_id`) ON DELETE CASCADE,
  CONSTRAINT `driver_applications_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `sponsor_organization` (`organization_id`) ON DELETE RESTRICT,
  CONSTRAINT `driver_applications_ibfk_3` FOREIGN KEY (`decided_by_user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `driver_sponsorships`
--

DROP TABLE IF EXISTS `driver_sponsorships`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `driver_sponsorships` (
  `driver_sponsorship_id` int NOT NULL AUTO_INCREMENT,
  `driver_id` int NOT NULL,
  `organization_id` int NOT NULL,
  `point_balance` int NOT NULL,
  `status` enum('PENDING','ACTIVE','PAUSED','DROPPED') NOT NULL,
  `create_time` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`driver_sponsorship_id`),
  UNIQUE KEY `uq_driver_sponsorship` (`driver_id`,`organization_id`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `driver_sponsorships_ibfk_1` FOREIGN KEY (`driver_id`) REFERENCES `drivers` (`driver_id`) ON DELETE CASCADE,
  CONSTRAINT `driver_sponsorships_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `sponsor_organization` (`organization_id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `drivers`
--

DROP TABLE IF EXISTS `drivers`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `drivers` (
  `driver_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `point_change_alert` tinyint(1) NOT NULL,
  `order_alert` tinyint(1) NOT NULL,
  `create_time` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`driver_id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `drivers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=32 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `login_attempts`
--

DROP TABLE IF EXISTS `login_attempts`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `login_attempts` (
  `attempt_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int DEFAULT NULL,
  `username_attempted` varchar(255) NOT NULL,
  `success` tinyint(1) NOT NULL,
  `attempt_time` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`attempt_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `login_attempts_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=309 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `notifications`
--

DROP TABLE IF EXISTS `notifications`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `notifications` (
  `notification_id` int NOT NULL AUTO_INCREMENT,
  `driver_id` int NOT NULL,
  `issued_by_user_id` int DEFAULT NULL,
  `category` enum('APPLICATION','DRIVER_DROPPED','POINT_CHANGE','ORDER_PLACED') NOT NULL,
  `message` text NOT NULL,
  `is_read` tinyint(1) NOT NULL,
  `create_time` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`notification_id`),
  KEY `driver_id` (`driver_id`),
  KEY `issued_by_user_id` (`issued_by_user_id`),
  CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`driver_id`) REFERENCES `drivers` (`driver_id`) ON DELETE CASCADE,
  CONSTRAINT `notifications_ibfk_2` FOREIGN KEY (`issued_by_user_id`) REFERENCES `users` (`user_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=31 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `order_items`
--

DROP TABLE IF EXISTS `order_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `order_items` (
  `item_id` int NOT NULL AUTO_INCREMENT,
  `order_id` int NOT NULL,
  `catalog_id` int NOT NULL,
  `quantity` int NOT NULL,
  `price` int NOT NULL,
  `create_time` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`item_id`),
  KEY `order_id` (`order_id`),
  KEY `catalog_id` (`catalog_id`),
  CONSTRAINT `order_items_ibfk_1` FOREIGN KEY (`order_id`) REFERENCES `orders` (`order_id`) ON DELETE CASCADE,
  CONSTRAINT `order_items_ibfk_2` FOREIGN KEY (`catalog_id`) REFERENCES `sponsor_catalog_items` (`catalog_id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=9 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `orders`
--

DROP TABLE IF EXISTS `orders`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `orders` (
  `order_id` int NOT NULL AUTO_INCREMENT,
  `driver_id` int NOT NULL,
  `organization_id` int NOT NULL,
  `placed_by_user_id` int NOT NULL,
  `points` int NOT NULL,
  `order_status` enum('PENDING','COMPLETED','CANCELLED') NOT NULL,
  `create_time` datetime NOT NULL DEFAULT (now()),
  `point_value_at_purchase` decimal(10,4) DEFAULT NULL,
  PRIMARY KEY (`order_id`),
  KEY `driver_id` (`driver_id`),
  KEY `organization_id` (`organization_id`),
  KEY `placed_by_user_id` (`placed_by_user_id`),
  CONSTRAINT `orders_ibfk_1` FOREIGN KEY (`driver_id`) REFERENCES `drivers` (`driver_id`) ON DELETE CASCADE,
  CONSTRAINT `orders_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `sponsor_organization` (`organization_id`) ON DELETE RESTRICT,
  CONSTRAINT `orders_ibfk_3` FOREIGN KEY (`placed_by_user_id`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=10 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `password_changes`
--

DROP TABLE IF EXISTS `password_changes`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `password_changes` (
  `pass_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `change_type` enum('RESET','UPDATE','ADMIN_RESET') NOT NULL,
  `change_time` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`pass_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `password_changes_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=13 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `point_transactions`
--

DROP TABLE IF EXISTS `point_transactions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `point_transactions` (
  `transaction_id` int NOT NULL AUTO_INCREMENT,
  `driver_id` int NOT NULL,
  `organization_id` int NOT NULL,
  `performed_by_user_id` int NOT NULL,
  `point_change` int NOT NULL,
  `reason` varchar(255) NOT NULL,
  `create_time` datetime NOT NULL DEFAULT (now()),
  PRIMARY KEY (`transaction_id`),
  KEY `driver_id` (`driver_id`),
  KEY `organization_id` (`organization_id`),
  KEY `performed_by_user_id` (`performed_by_user_id`),
  CONSTRAINT `point_transactions_ibfk_1` FOREIGN KEY (`driver_id`) REFERENCES `drivers` (`driver_id`) ON DELETE CASCADE,
  CONSTRAINT `point_transactions_ibfk_2` FOREIGN KEY (`organization_id`) REFERENCES `sponsor_organization` (`organization_id`) ON DELETE RESTRICT,
  CONSTRAINT `point_transactions_ibfk_3` FOREIGN KEY (`performed_by_user_id`) REFERENCES `users` (`user_id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=16 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sponsor_catalog_items`
--

DROP TABLE IF EXISTS `sponsor_catalog_items`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sponsor_catalog_items` (
  `catalog_id` int NOT NULL AUTO_INCREMENT,
  `organization_id` int NOT NULL,
  `external_id` int NOT NULL,
  `product_name` varchar(255) NOT NULL,
  `last_update` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `price` decimal(10,2) DEFAULT NULL,
  PRIMARY KEY (`catalog_id`),
  KEY `organization_id` (`organization_id`),
  CONSTRAINT `sponsor_catalog_items_ibfk_1` FOREIGN KEY (`organization_id`) REFERENCES `sponsor_organization` (`organization_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sponsor_organization`
--

DROP TABLE IF EXISTS `sponsor_organization`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sponsor_organization` (
  `organization_id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `point_value` decimal(10,4) NOT NULL DEFAULT '0.0100',
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `contact_email` varchar(255) DEFAULT NULL,
  `contact_phone` varchar(50) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `rules` text,
  PRIMARY KEY (`organization_id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `sponsor_users`
--

DROP TABLE IF EXISTS `sponsor_users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `sponsor_users` (
  `sponsor_id` int NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `organization_id` int NOT NULL,
  `create_time` datetime NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`sponsor_id`),
  UNIQUE KEY `uq_sponsor_user` (`user_id`),
  KEY `fk_sponsor_user_org` (`organization_id`),
  CONSTRAINT `fk_sponsor_user` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_sponsor_user_org` FOREIGN KEY (`organization_id`) REFERENCES `sponsor_organization` (`organization_id`) ON DELETE RESTRICT
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Table structure for table `users`
--

DROP TABLE IF EXISTS `users`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `users` (
  `user_id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(255) NOT NULL,
  `password` varchar(255) NOT NULL,
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `email` varchar(255) DEFAULT NULL,
  `role_type` enum('DRIVER','SPONSOR','ADMIN') NOT NULL,
  `first_name` varchar(255) DEFAULT NULL,
  `last_name` varchar(255) DEFAULT NULL,
  `is_user_active` tinyint(1) DEFAULT NULL,
  `failed_login_attempts` int NOT NULL DEFAULT '0',
  `is_login_locked` tinyint(1) NOT NULL DEFAULT '0',
  `locked_at` datetime DEFAULT NULL,
  `must_notify_password_reset` tinyint(1) NOT NULL DEFAULT '0',
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=85 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Final view structure for view `audit_log`
--

/*!50001 DROP VIEW IF EXISTS `audit_log`*/;
/*!50001 SET @saved_cs_client          = @@character_set_client */;
/*!50001 SET @saved_cs_results         = @@character_set_results */;
/*!50001 SET @saved_col_connection     = @@collation_connection */;
/*!50001 SET character_set_client      = utf8mb4 */;
/*!50001 SET character_set_results     = utf8mb4 */;
/*!50001 SET collation_connection      = utf8mb4_unicode_ci */;
/*!50001 CREATE ALGORITHM=UNDEFINED */
/*!50013 DEFINER=`CPSC4911_admin`@`%` SQL SECURITY DEFINER */
/*!50001 VIEW `audit_log` AS select `audit_base`.`user_id` AS `user_id`,`users`.`username` AS `username`,`users`.`role_type` AS `role_type`,`audit_base`.`type` AS `event_type`,`audit_base`.`detail` AS `detail`,`audit_base`.`event_time` AS `event_time`,ifnull(`driver_sponsorships`.`organization_id`,`sponsor_users`.`organization_id`) AS `organization_id`,`driver_sponsorships`.`status` AS `organization_status` from (((((select 'Login Attempt' AS `type`,`login_attempts`.`user_id` AS `user_id`,concat('Attempted username ',`login_attempts`.`username_attempted`,'. ',(case when `login_attempts`.`success` then 'Successful' else 'Unsuccessful' end),'.') AS `detail`,`login_attempts`.`attempt_time` AS `event_time` from `login_attempts` union select 'Point Transaction' AS `type`,`drivers`.`user_id` AS `user_id`,concat(`point_transactions`.`point_change`,' points added by ',`users`.`username`,'. Reason given: ',`point_transactions`.`reason`) AS `detail`,`point_transactions`.`create_time` AS `event_time` from ((`point_transactions` join `drivers` on((`point_transactions`.`driver_id` = `drivers`.`driver_id`))) left join `users` on((`point_transactions`.`performed_by_user_id` = `users`.`user_id`))) union select 'Password Change' AS `type`,`password_changes`.`user_id` AS `user_id`,concat('Changed password using ',`password_changes`.`change_type`,' method.') AS `detail`,`password_changes`.`change_time` AS `event_time` from `password_changes` union select 'Driver Application' AS `type`,`drivers`.`user_id` AS `user_id`,concat('Applied for organization ',`driver_applications`.`organization_id`,'. Application ',`driver_applications`.`status`,(case when (`driver_applications`.`status` <> 'PENDING') then concat(' by ',`users`.`username`) else '' end),'.') AS `detail`,`driver_applications`.`create_time` AS `event_time` from ((`driver_applications` join `drivers` on((`driver_applications`.`driver_id` = `drivers`.`driver_id`))) left join `users` on((`driver_applications`.`decided_by_user_id` = `users`.`user_id`)))) `audit_base` join `users` on((`audit_base`.`user_id` = `users`.`user_id`))) left join `drivers` on((`audit_base`.`user_id` = `drivers`.`user_id`))) left join `sponsor_users` on((`audit_base`.`user_id` = `sponsor_users`.`user_id`))) left join `driver_sponsorships` on((`drivers`.`driver_id` = `driver_sponsorships`.`driver_id`))) order by `audit_base`.`event_time` */;
/*!50001 SET character_set_client      = @saved_cs_client */;
/*!50001 SET character_set_results     = @saved_cs_results */;
/*!50001 SET collation_connection      = @saved_col_connection */;
SET @@SESSION.SQL_LOG_BIN = @MYSQLDUMP_TEMP_LOG_BIN;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-04-16  9:50:00
