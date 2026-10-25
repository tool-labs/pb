-- WP:PB database scheme
-- revision 3: matches the production database on ToolsDB (MariaDB 10.6) as of 2026-10.
-- `NULL` is spelled out for the TIMESTAMP columns because ToolsDB runs with
-- explicit_defaults_for_timestamp=OFF; without it MariaDB silently creates
-- NOT NULL columns with ON UPDATE CURRENT_TIMESTAMP.

DROP TABLE IF EXISTS `confirmation`;
DROP TABLE IF EXISTS `stats_confirmations_by_month`;
DROP TABLE IF EXISTS `user`;

-- table `user`
CREATE TABLE `user` (
  `user_id` int(11) unsigned NOT NULL,
  `user_name` varchar(255) NOT NULL,
  `user_comment` text DEFAULT NULL,
  `user_participates_since` timestamp NULL DEFAULT NULL,
  `user_verified_since` timestamp NULL DEFAULT NULL,
  `user_last_update` timestamp NOT NULL DEFAULT current_timestamp(),
  `user_is_hidden` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'This filed toggles if the participant wants to leave PB or not. It is not the right place for uncovered sockpuppets.',
  `user_was_banned` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'This filed toggles if the participant was ''deleted''/banned from PB or not. It is the right place for uncovered sockpuppets, but not for users were banned on WP.',
  UNIQUE KEY `user_name` (`user_name`),
  UNIQUE KEY `user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb3 COLLATE=utf8mb3_general_ci;

-- table `confirmation`
CREATE TABLE `confirmation` (
  `cf_user_id` int(11) unsigned NOT NULL,
  `cf_confirmed_user_id` int(11) unsigned NOT NULL,
  `cf_timestamp` timestamp NOT NULL DEFAULT current_timestamp(),
  `cf_comment` mediumtext DEFAULT NULL,
  `cf_was_deleted` int(1) unsigned NOT NULL DEFAULT 0 COMMENT 'e.g. when a sockpuppet was uncovered, not when a confirmation was made by mistake',
  PRIMARY KEY (`cf_user_id`,`cf_confirmed_user_id`),
  KEY `cf_confirmed_user_id` (`cf_confirmed_user_id`),
  KEY `cf_user_id` (`cf_user_id`),
  CONSTRAINT `confirmation_ibfk_1` FOREIGN KEY (`cf_user_id`) REFERENCES `user` (`user_id`),
  CONSTRAINT `confirmation_ibfk_2` FOREIGN KEY (`cf_confirmed_user_id`) REFERENCES `user` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- table `stats_confirmations_by_month`, filled hourly by jobs/update_stats.py
CREATE TABLE `stats_confirmations_by_month` (
  `year_month` varchar(255) NOT NULL,
  `group` int(2) NOT NULL,
  `count` int(6) unsigned NOT NULL,
  UNIQUE KEY `year_month` (`year_month`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
