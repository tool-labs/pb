-- WP:PB database scheme

-- database `p_wppb`
-- CREATE DATABASE IF NOT EXISTS `p_wppb`;
USE `p_wppb`;

-- table `user`
DROP TABLE IF EXISTS `user`;
CREATE TABLE `user` (
  `user_id` int(11) unsigned NOT NULL,
  `user_name` varchar(255) NOT NULL,
  `user_comment` text DEFAULT NULL,
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
  PRIMARY KEY (`cf_user_id`, `cf_confirmed_user_id`),
  FOREIGN KEY (`cf_user_id`) REFERENCES `user`(`user_id`),
  FOREIGN KEY (`cf_confirmed_user_id`) REFERENCES `user`(`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=UTF9 ;

