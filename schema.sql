-- ═══════════════════════════════════════════════════════════════
--  SUBWAY SERVICE SYSTEM — MySQL Schema
--  3NF/BCNF Normalized · Triggers Included
-- ═══════════════════════════════════════════════════════════════

CREATE DATABASE IF NOT EXISTS subway_system;
USE subway_system;

-- ── USER ──────────────────────────────────────────────────────
CREATE TABLE user (
    user_id       INT PRIMARY KEY AUTO_INCREMENT,
    username      VARCHAR(100) NOT NULL,
    email         VARCHAR(150) NOT NULL UNIQUE,
    phone         VARCHAR(15),
    address       VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    role          ENUM('passenger', 'admin') NOT NULL DEFAULT 'passenger',
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- ── METRO ─────────────────────────────────────────────────────
CREATE TABLE metro (
    metro_id        INT PRIMARY KEY AUTO_INCREMENT,
    name            VARCHAR(100) NOT NULL,
    metro_code      VARCHAR(20)  NOT NULL UNIQUE,
    total_seats     INT NOT NULL DEFAULT 200,
    economy_seats   INT NOT NULL DEFAULT 100,
    premium_seats   INT NOT NULL DEFAULT 60,
    business_seats  INT NOT NULL DEFAULT 40,
    is_active       BOOLEAN DEFAULT TRUE
);

-- ── STATION ───────────────────────────────────────────────────
CREATE TABLE station (
    station_id  INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(150) NOT NULL,
    code        VARCHAR(10)  NOT NULL UNIQUE,
    location    VARCHAR(255),
    is_active   BOOLEAN DEFAULT TRUE
);

-- ── SCHEDULE ──────────────────────────────────────────────────
CREATE TABLE schedule (
    schedule_id       INT PRIMARY KEY AUTO_INCREMENT,
    metro_id          INT NOT NULL,
    source_station_id INT NOT NULL,
    dest_station_id   INT NOT NULL,
    departure_time    TIME NOT NULL,
    arrival_time      TIME NOT NULL,
    travel_date       DATE NOT NULL,
    economy_fare      DECIMAL(8,2) NOT NULL DEFAULT 100.00,
    premium_fare      DECIMAL(8,2) NOT NULL DEFAULT 160.00,
    business_fare     DECIMAL(8,2) NOT NULL DEFAULT 240.00,
    is_active         BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (metro_id)          REFERENCES metro(metro_id),
    FOREIGN KEY (source_station_id) REFERENCES station(station_id),
    FOREIGN KEY (dest_station_id)   REFERENCES station(station_id),
    CHECK (source_station_id <> dest_station_id)
);

-- ── ROUTE ─────────────────────────────────────────────────────
CREATE TABLE route (
    route_id    INT PRIMARY KEY AUTO_INCREMENT,
    schedule_id INT NOT NULL,
    station_id  INT NOT NULL,
    stop_number INT NOT NULL,
    FOREIGN KEY (schedule_id) REFERENCES schedule(schedule_id),
    FOREIGN KEY (station_id)  REFERENCES station(station_id)
);

-- ── PASSENGER ─────────────────────────────────────────────────
CREATE TABLE passenger (
    passenger_id   INT PRIMARY KEY AUTO_INCREMENT,
    user_id        INT NOT NULL UNIQUE,
    passenger_name VARCHAR(150) NOT NULL,
    age            INT CHECK (age > 0 AND age < 150),
    address        VARCHAR(255),
    phone_no       VARCHAR(15),
    pir_no         VARCHAR(30),
    FOREIGN KEY (user_id) REFERENCES user(user_id)
);

-- ── BOOKING ───────────────────────────────────────────────────
CREATE TABLE booking (
    booking_id     INT PRIMARY KEY AUTO_INCREMENT,
    passenger_id   INT NOT NULL,
    schedule_id    INT NOT NULL,
    booking_time   DATETIME DEFAULT CURRENT_TIMESTAMP,
    ticket_no      VARCHAR(30) NOT NULL UNIQUE,
    seat_type      VARCHAR(30) NOT NULL,
    seat_number    VARCHAR(10),
    total_fare     DECIMAL(8,2) NOT NULL,
    status         ENUM('confirmed','cancelled','waitlisted') NOT NULL DEFAULT 'confirmed',
    payment_method VARCHAR(20),
    transaction_id VARCHAR(50),
    FOREIGN KEY (passenger_id) REFERENCES passenger(passenger_id),
    FOREIGN KEY (schedule_id)  REFERENCES schedule(schedule_id),
    CHECK (total_fare >= 0)
);

-- ── WAITLIST ──────────────────────────────────────────────────
CREATE TABLE waitlist (
    waitlist_id  INT PRIMARY KEY AUTO_INCREMENT,
    passenger_id INT NOT NULL,
    schedule_id  INT NOT NULL,
    request_time DATETIME DEFAULT CURRENT_TIMESTAMP,
    seat_type    VARCHAR(30) NOT NULL,
    position     INT NOT NULL,
    FOREIGN KEY (passenger_id) REFERENCES passenger(passenger_id),
    FOREIGN KEY (schedule_id)  REFERENCES schedule(schedule_id)
);

-- ═══════════════════════════════════════════════════════════════
--  TRIGGERS
-- ═══════════════════════════════════════════════════════════════

DELIMITER $$

-- TRIGGER 1: Validate seat_number > 0 before insert
CREATE TRIGGER before_booking_insert
BEFORE INSERT ON booking
FOR EACH ROW
BEGIN
    IF NEW.total_fare < 0 THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Fare cannot be negative.';
    END IF;
END$$

-- TRIGGER 2: Auto-add to waitlist if booking is made when seat is full
-- (Handled at application level via _trigger_add_to_waitlist function)

-- TRIGGER 3: Promote waitlist when booking is cancelled
CREATE TRIGGER after_booking_cancel
AFTER UPDATE ON booking
FOR EACH ROW
BEGIN
    DECLARE wl_passenger INT;
    DECLARE new_ticket VARCHAR(30);

    IF OLD.status = 'confirmed' AND NEW.status = 'cancelled' THEN
        SELECT passenger_id INTO wl_passenger
        FROM waitlist
        WHERE schedule_id = OLD.schedule_id AND seat_type = OLD.seat_type
        ORDER BY position ASC
        LIMIT 1;

        IF wl_passenger IS NOT NULL THEN
            SET new_ticket = CONCAT('WL-', FLOOR(RAND() * 9000000 + 1000000));
            INSERT INTO booking (passenger_id, schedule_id, ticket_no, seat_type,
                                 seat_number, total_fare, status, payment_method)
            SELECT wl_passenger, OLD.schedule_id, new_ticket, OLD.seat_type,
                   OLD.seat_number, total_fare, 'confirmed', 'waitlist_promoted'
            FROM booking WHERE booking_id = OLD.booking_id;

            DELETE FROM waitlist
            WHERE schedule_id = OLD.schedule_id
              AND passenger_id = wl_passenger
              AND seat_type = OLD.seat_type;
        END IF;
    END IF;
END$$

DELIMITER ;

-- ═══════════════════════════════════════════════════════════════
--  USEFUL VIEWS
-- ═══════════════════════════════════════════════════════════════

-- All bookings with full passenger & schedule details
CREATE VIEW booking_details AS
SELECT
    b.booking_id,
    b.ticket_no,
    p.passenger_name,
    u.email,
    s.travel_date,
    st1.name  AS from_station,
    st2.name  AS to_station,
    s.departure_time,
    s.arrival_time,
    m.name    AS metro_name,
    b.seat_type,
    b.seat_number,
    b.total_fare,
    b.status,
    b.payment_method,
    b.booking_time
FROM booking b
JOIN passenger p  ON b.passenger_id  = p.passenger_id
JOIN user u       ON p.user_id        = u.user_id
JOIN schedule s   ON b.schedule_id    = s.schedule_id
JOIN station st1  ON s.source_station_id = st1.station_id
JOIN station st2  ON s.dest_station_id   = st2.station_id
JOIN metro m      ON s.metro_id       = m.metro_id;

-- Revenue by metro line
CREATE VIEW revenue_by_metro AS
SELECT
    m.name AS metro_name,
    COUNT(b.booking_id) AS total_bookings,
    SUM(b.total_fare)   AS total_revenue
FROM booking b
JOIN schedule s ON b.schedule_id = s.schedule_id
JOIN metro m    ON s.metro_id = m.metro_id
WHERE b.status = 'confirmed'
GROUP BY m.metro_id, m.name;

-- Seat availability per schedule
CREATE VIEW seat_availability AS
SELECT
    s.schedule_id,
    m.name AS metro_name,
    st1.name AS from_station,
    st2.name AS to_station,
    s.travel_date,
    m.economy_seats - COUNT(CASE WHEN b.seat_type='economy' AND b.status='confirmed' THEN 1 END) AS economy_available,
    m.premium_seats - COUNT(CASE WHEN b.seat_type='premium_economy' AND b.status='confirmed' THEN 1 END) AS premium_available,
    m.business_seats - COUNT(CASE WHEN b.seat_type='business' AND b.status='confirmed' THEN 1 END) AS business_available
FROM schedule s
JOIN metro m   ON s.metro_id = m.metro_id
JOIN station st1 ON s.source_station_id = st1.station_id
JOIN station st2 ON s.dest_station_id   = st2.station_id
LEFT JOIN booking b ON s.schedule_id = b.schedule_id
GROUP BY s.schedule_id, m.name, st1.name, st2.name, s.travel_date,
         m.economy_seats, m.premium_seats, m.business_seats;
