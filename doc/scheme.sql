-- WP:PB database scheme
-- revision 2

-- table `user`
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `user_id` int(11) unsigned NOT NULL,
  `user_name` varchar(255) NOT NULL,
  `user_comment` text DEFAULT NULL,
  `user_participates_since` timestamp DEFAULT NULL,
  `user_verified_since` timestamp DEFAULT NULL,
  `user_last_update` timestamp DEFAULT CURRENT_TIMESTAMP(),
  `user_is_hidden` int(1) unsigned NOT NULL DEFAULT 0,
  `user_was_banned` int(1) unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `user_name` (`user_name`)
) ENGINE=InnoDB DEFAULT CHARSET=UTF8 ;

-- table `confirmation`
DROP TABLE IF EXISTS `confirmation`;
CREATE TABLE `confirmation` (
  `cf_user_id` int(11) unsigned NOT NULL,
  `cf_confirmed_user_id` int(11) unsigned NOT NULL,
  `cf_timestamp` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP(),
  `cf_comment` text DEFAULT NULL,
  `cf_was_deleted` int(1) unsigned NOT NULL DEFAULT 0,
  PRIMARY KEY (`cf_user_id`, `cf_confirmed_user_id`),
  FOREIGN KEY (`cf_user_id`) REFERENCES `user`(`user_id`),
  FOREIGN KEY (`cf_confirmed_user_id`) REFERENCES `user`(`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=UTF8 ;

