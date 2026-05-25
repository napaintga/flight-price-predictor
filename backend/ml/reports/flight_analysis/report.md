# Детальний аналіз авіаквитків

Згенеровано: 2026-04-25T23:32:39
Джерело даних: `etl\exports\flights_features_all.csv`

## Ключові автоматичні висновки

- Найнижча медіанна ціна у вікні бронювання `15-30`: 560.
- Святкова медіанна націнка: -18.7% відносно не святкових дат.
- Медіанна різниця для вильотів у вихідні: 4.9%.
- Медіанна різниця прямих рейсів проти непрямих: -57.2%.
- Найпопулярніший маршрут: `LHR -> FCO` з 153,637 пасажирами.
- Найбільший revenue proxy дає маршрут `WAW -> CDG`: 126,155,153.00.
- Найсильніша проста числова кореляція з ціною: `stops` (0.329).
- У моделі найважливіший фактор: `travel_class` (importance 0.523).

## Огляд даних

| metric | value |
| --- | --- |
| raw_rows | 5,150,048 |
| valid_rows | 5,119,917 |
| dropped_rows | 30,131 |
| columns | 44 |
| unique_flights | 1,041,047 |
| unique_routes | 57 |
| unique_airlines | 318 |
| departure_date_min | 2026-02-18 |
| departure_date_max | 2026-05-21 |
| avg_price | 842.36 |
| median_price | 619 |
| min_price | 19 |

## Якість даних та аномалії

| check | rows | share_pct | column |
| --- | --- | --- | --- |
| Rows rejected by validity filter | 30,131 | 0.585 |  |
| Duplicate full rows | 485,335 | 9.424 |  |
| Duplicate flight_id values | 4,103,802 | 79.685 |  |
| Duplicate ticket-like key | 1,782,003 | 34.602 |  |
| Non-positive price | 11,040 | 0.214 | price |
| Non-positive distance_km | 0 | 0 | distance_km |
| Non-positive duration_minutes | 0 | 0 | duration_minutes |
| Negative days_to_departure | 0 | 0 | days_to_departure |
| Negative stops | 0 | 0 | stops |
| Non-positive passengers_total | 0 | 0 | passengers_total |
| Suspicious avg_speed_kmh below 100 | 2,626,807 | 51.005 | avg_speed_kmh |
| Suspicious avg_speed_kmh above 1200 | 0 | 0 | avg_speed_kmh |
| Short route with 2+ stops | 70,256 | 1.364 | distance_km/stops |
| High price_per_km outlier by 3*IQR | 219,995 | 4.272 | price_per_km |

### Найбільші пропуски

| column | missing_rows | missing_pct |
| --- | --- | --- |
| price_segment | 30,131 | 0.585 |
| price_per_hour | 30,115 | 0.585 |
| price | 19,091 | 0.371 |
| price_per_km | 19,091 | 0.371 |
| revenue_proxy | 19,091 | 0.371 |
| avg_speed_kmh | 11,024 | 0.214 |
| depart_hour | 11,024 | 0.214 |
| duration_minutes | 11,024 | 0.214 |
| duration_per_1000km | 11,024 | 0.214 |
| is_direct | 11,024 | 0.214 |
| stops | 11,024 | 0.214 |
| airline | 0 | 0 |

## Метрики ціни

| metric | value |
| --- | --- |
| count | 5,119,917.00 |
| mean | 842.36 |
| median | 619 |
| std | 848.305 |
| min | 19 |
| q25 | 361 |
| q75 | 962 |
| p90 | 1,563.00 |
| p95 | 2,166.00 |
| p99 | 4,653.00 |
| max | 9,605.00 |
| coefficient_of_variation | 1.007 |

## Ціна за ключовими категоріями

### Клас подорожі

| travel_class | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Economy Class | 2,667,868 | 2,667,876 | 510.217 | 376 | 886 | 1,180.93 | 774.793 | 1.194 | 0.516 | 0.33 | 49.398 | 1,361,196,810.00 |
| Business Class | 2,319,781 | 2,319,781 | 1,143.51 | 891 | 1,851.00 | 1,194.11 | 776.104 | 1.219 | 1.13 | 0.783 | 111.641 | 2,652,687,741.00 |
| Premium Economy | 132,268 | 132,268 | 2,260.06 | 618 | 5,812.30 | 1,101.74 | 739.475 | 1.323 | 2.102 | 1.128 | 217.207 | 298,933,751.00 |

### Пересадки

| stop_bucket | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 stop | 3,782,221 | 3,782,227 | 704.578 | 572 | 1,312.00 | 1,189.21 | 793.264 | 1 | 0.715 | 0.503 | 66.924 | 2,664,874,982.00 |
| 2 stops | 1,155,364 | 1,155,364 | 1,322.59 | 897 | 3,324.00 | 1,181.88 | 796.928 | 2 | 1.26 | 0.821 | 116.351 | 1,528,076,118.00 |
| direct | 150,523 | 150,525 | 378.701 | 269 | 829 | 1,103.68 | 132.973 | 0 | 0.406 | 0.276 | 175.983 | 57,004,069.00 |
| 3+ stops | 31,809 | 31,809 | 1,976.27 | 1,480.00 | 4,517.00 | 1,159.55 | 760.453 | 3.02 | 1.733 | 1.281 | 171.702 | 62,863,133.00 |

### Сезон вильоту

| depart_season_name | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Spring | 4,943,754 | 4,943,754 | 840.358 | 617 | 1,559.00 | 1,184.43 | 774.527 | 1.209 | 0.834 | 0.542 | 81.656 | 4,154,523,364.00 |
| Winter | 176,163 | 176,171 | 898.545 | 712 | 1,647.00 | 1,196.74 | 773.014 | 1.193 | 0.867 | 0.614 | 89.763 | 158,294,938.00 |

### Вікно бронювання

| days_to_departure_bucket | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0-3 | 400,191 | 400,199 | 1,010.08 | 846 | 1,810.00 | 1,194.38 | 736.479 | 1.165 | 0.979 | 0.726 | 106.729 | 404,227,719.00 |
| 4-7 | 771,431 | 771,431 | 945.524 | 715 | 1,755.00 | 1,181.93 | 780.316 | 1.217 | 0.935 | 0.642 | 92.697 | 729,406,620.00 |
| 8-14 | 1,335,694 | 1,335,694 | 859.647 | 652 | 1,574.00 | 1,184.87 | 778.307 | 1.217 | 0.852 | 0.57 | 83.1 | 1,148,225,346.00 |
| 15-30 | 2,612,601 | 2,612,601 | 777.37 | 560 | 1,386.00 | 1,184.26 | 776.611 | 1.209 | 0.775 | 0.496 | 74.364 | 2,030,958,617.00 |
| 31-60 | 0 | 0 |  |  |  |  |  |  |  |  |  | 0 |
| 61-90 | 0 | 0 |  |  |  |  |  |  |  |  |  | 0 |
| 90+ | 0 | 0 |  |  |  |  |  |  |  |  |  | 0 |

## Попит і маршрути

### Top маршрути за пасажирами

| route | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy | direct_share_pct | avg_duration_per_1000km |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LHR -> FCO | 153,637 | 153,637 | 598.415 | 538 | 1,001.40 | 1,444.08 | 617.003 | 0.966 | 0.414 | 0.373 | 75.58 | 91,938,759.00 | 6.952 | 427.263 |
| LHR -> BCN | 150,957 | 150,957 | 544.32 | 497 | 878 | 1,147.70 | 648.234 | 0.938 | 0.474 | 0.433 | 70.996 | 82,168,936.00 | 7.264 | 564.81 |
| LHR -> NCE | 144,601 | 144,601 | 663.425 | 533 | 1,159.00 | 1,041.00 | 683.538 | 0.981 | 0.637 | 0.512 | 79.577 | 95,931,891.00 | 5.371 | 656.619 |
| LHR -> CDG | 143,605 | 143,605 | 598.811 | 537 | 1,024.00 | 347.613 | 547.84 | 0.915 | 1.723 | 1.545 | 93.71 | 85,992,211.00 | 10.509 | 1,576.01 |
| LHR -> MXP | 137,500 | 137,500 | 683.218 | 516 | 1,348.00 | 936.28 | 684.945 | 1.061 | 0.73 | 0.551 | 73.27 | 93,942,408.00 | 2.057 | 731.56 |
| LHR -> MAD | 132,666 | 132,666 | 600.945 | 519 | 1,033.00 | 1,243.79 | 633.923 | 0.915 | 0.483 | 0.417 | 80.95 | 79,724,977.00 | 11.223 | 509.672 |
| MAN -> FCO | 130,327 | 130,327 | 771.48 | 601 | 1,391.00 | 1,677.55 | 728.384 | 1.162 | 0.46 | 0.358 | 76.046 | 100,544,661.00 | 0.557 | 434.195 |
| LHR -> VCE | 128,844 | 128,844 | 608.012 | 518 | 1,218.00 | 1,151.32 | 659.966 | 1.018 | 0.528 | 0.45 | 74.764 | 78,338,717.00 | 4.236 | 573.226 |
| WAW -> CDG | 128,412 | 128,412 | 982.425 | 656 | 1,925.00 | 1,342.38 | 629.352 | 1.036 | 0.732 | 0.489 | 116.622 | 126,155,153.00 | 5.893 | 468.835 |
| MAN -> NCE | 126,256 | 126,256 | 838.1 | 647 | 1,526.00 | 1,282.31 | 804.514 | 1.139 | 0.654 | 0.505 | 78.02 | 105,815,146.00 | 0.467 | 627.396 |
| MAN -> CDG | 124,813 | 124,813 | 716.81 | 540 | 1,320.00 | 588.314 | 677.309 | 1.047 | 1.218 | 0.918 | 83.112 | 89,467,218.00 | 5.155 | 1,151.27 |
| WAW -> BCN | 124,360 | 124,360 | 748.206 | 536 | 1,250.00 | 1,869.69 | 721.368 | 1.06 | 0.4 | 0.287 | 73.162 | 93,046,866.00 | 1.51 | 385.822 |
| MAN -> BCN | 122,121 | 122,121 | 662.755 | 554 | 1,192.00 | 1,379.16 | 789.346 | 1.049 | 0.481 | 0.402 | 63.108 | 80,936,253.00 | 3.14 | 572.34 |
| WAW -> FCO | 122,040 | 122,040 | 709.729 | 547 | 1,109.00 | 1,326.14 | 673.207 | 1.132 | 0.535 | 0.412 | 73.719 | 86,615,385.00 | 2.533 | 507.645 |
| LHR -> MRS | 118,350 | 118,350 | 893.116 | 605 | 1,585.00 | 989.063 | 684.519 | 1.087 | 0.903 | 0.612 | 100.038 | 105,700,299.00 | 3.31 | 692.088 |

### Top маршрути за revenue proxy

| route | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| WAW -> CDG | 128,412 | 128,412 | 982.425 | 656 | 1,925.00 | 1,342.38 | 629.352 | 1.036 | 0.732 | 0.489 | 116.622 | 126,155,153.00 |
| WAW -> NCE | 113,370 | 113,370 | 965.435 | 697 | 1,671.00 | 1,390.48 | 754.745 | 1.135 | 0.694 | 0.501 | 92.886 | 109,451,420.00 |
| MAN -> MRS | 98,348 | 98,348 | 1,106.49 | 688 | 2,256.00 | 1,231.53 | 828.174 | 1.208 | 0.898 | 0.559 | 99.41 | 108,820,827.00 |
| WAW -> MRS | 99,803 | 99,803 | 1,064.29 | 815 | 2,113.00 | 1,519.60 | 759.886 | 1.274 | 0.7 | 0.536 | 102.104 | 106,219,780.00 |
| MAN -> NCE | 126,256 | 126,256 | 838.1 | 647 | 1,526.00 | 1,282.31 | 804.514 | 1.139 | 0.654 | 0.505 | 78.02 | 105,815,146.00 |
| LHR -> MRS | 118,350 | 118,350 | 893.116 | 605 | 1,585.00 | 989.063 | 684.519 | 1.087 | 0.903 | 0.612 | 100.038 | 105,700,299.00 |
| MAN -> FCO | 130,327 | 130,327 | 771.48 | 601 | 1,391.00 | 1,677.55 | 728.384 | 1.162 | 0.46 | 0.358 | 76.046 | 100,544,661.00 |
| WAW -> MXP | 100,006 | 100,006 | 995.153 | 627 | 1,831.00 | 1,149.98 | 700.584 | 1.182 | 0.865 | 0.545 | 104.31 | 99,521,221.00 |
| WAW -> MAD | 111,546 | 111,546 | 878.841 | 647 | 1,701.00 | 2,270.09 | 757.218 | 1.125 | 0.387 | 0.285 | 82.467 | 98,031,230.00 |
| MAN -> MXP | 105,065 | 105,065 | 919.268 | 614 | 1,760.00 | 1,167.39 | 839.105 | 1.15 | 0.787 | 0.526 | 81.901 | 96,582,890.00 |
| LGW -> FCO | 106,910 | 106,910 | 899.846 | 713 | 1,793.00 | 1,405.73 | 920.708 | 1.34 | 0.64 | 0.507 | 70.789 | 96,202,583.00 |
| LHR -> NCE | 144,601 | 144,601 | 663.425 | 533 | 1,159.00 | 1,041.00 | 683.538 | 0.981 | 0.637 | 0.512 | 79.577 | 95,931,891.00 |
| KTW -> NCE | 50,002 | 50,002 | 1,900.57 | 1,427.00 | 4,347.00 | 1,173.21 | 906.623 | 1.86 | 1.62 | 1.216 | 152.585 | 95,032,267.00 |
| LHR -> MXP | 137,500 | 137,500 | 683.218 | 516 | 1,348.00 | 936.28 | 684.945 | 1.061 | 0.73 | 0.551 | 73.27 | 93,942,408.00 |
| MAN -> VCE | 105,479 | 105,479 | 886.244 | 618 | 1,601.00 | 1,366.78 | 782.551 | 1.188 | 0.648 | 0.452 | 83.174 | 93,480,162.00 |

### Авіакомпанії за попитом

| airline | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Lufthansa | 539,343 | 539,344 | 628.343 | 510 | 1,175.00 | 1,311.78 | 713.202 | 1.157 | 0.541 | 0.393 | 64.531 | 338,893,900.00 |
| Air France | 350,143 | 350,144 | 577.877 | 532 | 938 | 1,234.84 | 582.288 | 0.97 | 0.494 | 0.426 | 81.069 | 202,339,911.00 |
| British Airways | 339,761 | 339,761 | 671.483 | 594 | 1,173.00 | 1,256.64 | 738.21 | 0.844 | 0.568 | 0.501 | 91 | 228,143,595.00 |
| SWISS | 279,943 | 279,944 | 730.962 | 585 | 1,486.00 | 1,150.17 | 843.41 | 1.043 | 0.733 | 0.517 | 65.945 | 204,628,410.00 |
| TAP Air Portugal | 242,486 | 242,486 | 605.665 | 550 | 1,019.00 | 985.132 | 994.834 | 1.186 | 0.885 | 0.561 | 43.085 | 146,865,380.00 |
| British Airways, Iberia | 225,894 | 225,894 | 870.113 | 824 | 1,414.00 | 1,095.83 | 781.573 | 1.45 | 1.08 | 0.745 | 77.475 | 196,553,240.00 |
| KLM | 208,895 | 208,895 | 587.378 | 611 | 939 | 1,319.73 | 501.945 | 1 | 0.492 | 0.418 | 81.471 | 122,700,231.00 |
| Turkish Airlines | 203,235 | 203,235 | 1,028.07 | 896 | 1,956.00 | 1,145.18 | 943.639 | 1 | 1.099 | 0.776 | 74.264 | 208,940,016.00 |
| Air Dolomiti, Lufthansa | 194,987 | 194,987 | 816.639 | 610 | 1,725.00 | 1,185.10 | 764.53 | 1.309 | 0.718 | 0.527 | 78.829 | 159,234,007.00 |
| Scandinavian Airlines | 171,146 | 171,146 | 872.128 | 615 | 1,136.00 | 1,137.90 | 871.558 | 1.074 | 0.89 | 0.524 | 69.682 | 149,261,174.00 |
| Iberia | 169,992 | 169,992 | 701.255 | 654 | 1,208.00 | 930.75 | 893.822 | 0.933 | 1.064 | 0.702 | 66.295 | 119,207,806.00 |
| Vueling | 162,201 | 162,201 | 323.569 | 312 | 498 | 832.703 | 881.439 | 0.933 | 0.579 | 0.355 | 29.926 | 52,483,209.00 |
| LOT Polish Airlines | 141,052 | 141,054 | 600.08 | 495 | 1,054.00 | 1,257.40 | 824.531 | 0.927 | 0.57 | 0.4 | 70.275 | 84,643,262.00 |
| Lufthansa, Lufthansa City Airlines | 127,691 | 127,691 | 565.482 | 455 | 978 | 1,197.59 | 609.113 | 1.142 | 0.579 | 0.424 | 66.603 | 72,206,977.00 |
| Brussels Airlines | 104,482 | 104,482 | 724.072 | 545 | 1,498.00 | 1,295.54 | 840.9 | 1 | 0.631 | 0.436 | 68.507 | 75,652,542.00 |

## Пошукова поведінка

### День пошуку

| search_dow_name | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Mon | 1,780,370 | 1,780,370 | 825.363 | 601 | 1,535.00 | 1,185.45 | 777.487 | 1.211 | 0.819 | 0.53 | 79.886 | 1,469,451,812.00 |
| Wed | 1,032,346 | 1,032,346 | 845.418 | 626 | 1,554.00 | 1,185.52 | 773.897 | 1.211 | 0.841 | 0.547 | 82.3 | 872,764,377.00 |
| Sat | 967,950 | 967,950 | 831.664 | 605 | 1,561.00 | 1,186.15 | 781.128 | 1.21 | 0.82 | 0.533 | 80.168 | 805,009,463.00 |
| Thu | 777,265 | 777,273 | 845.373 | 627 | 1,554.00 | 1,181.54 | 766.929 | 1.204 | 0.843 | 0.551 | 82.773 | 657,083,321.00 |
| Tue | 324,776 | 324,776 | 924.485 | 691 | 1,679.00 | 1,184.66 | 773.255 | 1.206 | 0.915 | 0.609 | 90.418 | 300,250,695.00 |
| Fri | 144,175 | 144,175 | 874.082 | 658 | 1,647.00 | 1,185.08 | 753.419 | 1.198 | 0.858 | 0.589 | 88.061 | 126,020,767.00 |
| Sun | 93,035 | 93,035 | 883.945 | 652 | 1,711.00 | 1,180.93 | 753.95 | 1.195 | 0.869 | 0.595 | 89.37 | 82,237,867.00 |

### Місяць пошуку

| search_month | records | total_passengers | avg_price | median_price | p90_price | avg_distance_km | avg_duration_minutes | avg_stops | avg_price_per_km | median_price_per_km | avg_price_per_hour | total_revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 975,807.00 | 975,815.00 | 802.883 | 558 | 1,527.00 | 1,191.08 | 794.368 | 1.22 | 0.787 | 0.5 | 76.261 | 783,463,104.00 |
| 3 | 1,371,323.00 | 1,371,323.00 | 824.531 | 612 | 1,514.00 | 1,187.12 | 773.333 | 1.215 | 0.819 | 0.536 | 80.469 | 1,130,698,757.00 |
| 4 | 2,772,787.00 | 2,772,787.00 | 865.071 | 637 | 1,610.00 | 1,181.55 | 768.039 | 1.202 | 0.86 | 0.565 | 84.657 | 2,398,656,441.00 |

## Кореляції

| metric | price | days_to_departure | distance_km | duration_minutes | passengers_total | depart_hour | stops | price_per_km | price_per_hour | avg_speed_kmh | revenue_proxy |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| price | 1 | -0.087 | 0.046 | 0.076 | -0 | 0.008 | 0.329 | 0.794 | 0.782 | -0.091 | 1 |
| days_to_departure | -0.087 | 1 | -0.003 | 0.009 | -0.002 | -0.006 | 0.004 | -0.074 | -0.096 | -0.014 | -0.087 |
| distance_km | 0.046 | -0.003 | 1 | -0.048 | -0.001 | -0.049 | 0.007 | -0.393 | 0.029 | 0.406 | 0.046 |
| duration_minutes | 0.076 | 0.009 | -0.048 | 1 | -0.002 | 0.319 | 0.124 | 0.1 | -0.357 | -0.692 | 0.076 |
| passengers_total | -0 | -0.002 | -0.001 | -0.002 | 1 | 0.001 | -0.001 | -0 | 0.001 | 0.002 | 0 |
| depart_hour | 0.008 | -0.006 | -0.049 | 0.319 | 0.001 | 1 | -0.148 | 0.03 | -0.126 | -0.172 | 0.008 |
| stops | 0.329 | 0.004 | 0.007 | 0.124 | -0.001 | -0.148 | 1 | 0.269 | 0.136 | -0.33 | 0.329 |
| price_per_km | 0.794 | -0.074 | -0.393 | 0.1 | -0 | 0.03 | 0.269 | 1 | 0.615 | -0.261 | 0.794 |
| price_per_hour | 0.782 | -0.096 | 0.029 | -0.357 | 0.001 | -0.126 | 0.136 | 0.615 | 1 | 0.321 | 0.782 |
| avg_speed_kmh | -0.091 | -0.014 | 0.406 | -0.692 | 0.002 | -0.172 | -0.33 | -0.261 | 0.321 | 1 | -0.091 |
| revenue_proxy | 1 | -0.087 | 0.046 | 0.076 | 0 | 0.008 | 0.329 | 0.794 | 0.782 | -0.091 | 1 |

## Статистичні тести

| test | group_0_n | group_1_n | group_0_mean | group_1_mean | group_0_median | group_1_median | statistic | p_value | groups | group_count | degrees_of_freedom |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Holiday vs non-holiday departure: Welch t-test | 199,995.00 | 5 | 843.863 | 817 | 618 | 800 | -1.589 | 0.185 |  |  |  |
| Holiday vs non-holiday departure: Mann-Whitney U | 199,995.00 | 5 | 843.863 | 817 | 618 | 800 | 658,415.50 | 0.22 |  |  |  |
| Weekend vs weekday departure: Welch t-test | 143,759.00 | 56,241.00 | 830.369 | 878.354 | 609 | 640 | 11.055 | 0 |  |  |  |
| Weekend vs weekday departure: Mann-Whitney U | 143,759.00 | 56,241.00 | 830.369 | 878.354 | 609 | 640 | 4,237,735,686.00 | 0 |  |  |  |
| Weekend vs weekday search: Welch t-test | 158,670.00 | 41,330.00 | 844.467 | 841.541 | 621 | 609 | -0.611 | 0.542 |  |  |  |
| Weekend vs weekday search: Mann-Whitney U | 158,670.00 | 41,330.00 | 844.467 | 841.541 | 621 | 609 | 3,216,901,869.50 | 0 |  |  |  |
| Departure day of week: Kruskal-Wallis |  |  |  |  |  |  | 815.946 | 0 | Fri, Mon, Sat, Sun, Thu, Tue, Wed | 7 |  |
| Departure season: Kruskal-Wallis |  |  |  |  |  |  | 138.49 | 0 | Spring, Winter | 2 |  |
| Travel class: Kruskal-Wallis |  |  |  |  |  |  | 83,314.83 | 0 | Business Class, Economy Class, Premium Economy | 3 |  |
| Stops: Kruskal-Wallis |  |  |  |  |  |  | 18,987.16 | 0 | 1 stop, 2 stops, 3+ stops, direct | 4 |  |
| depart_season x stops: chi-square |  |  |  |  |  |  | 32.562 | 0 |  |  | 3 |

## Модель факторів ціни

| metric | value |
| --- | --- |
| rows_used | 50,000 |
| features_used | 13 |
| target | log1p(price) |
| model | RandomForestRegressor |
| mae | 256.713 |
| rmse | 532.405 |
| r2 | 0.593 |
| baseline_median_mae | 465.173 |

### Feature importance

| source_feature | importance |
| --- | --- |
| travel_class | 0.523 |
| stops | 0.152 |
| airline | 0.135 |
| days_to_departure | 0.039 |
| origin | 0.033 |
| duration_minutes | 0.03 |
| depart_hour | 0.021 |
| destination | 0.019 |
| distance_km | 0.019 |
| search_month | 0.012 |
| arrival_time | 0.007 |
| depart_dow_name | 0.006 |
| depart_month | 0.004 |

## Вихідні файли

- `tables/anomaly_high_price.csv`
- `tables/anomaly_high_price_per_km.csv`
- `tables/anomaly_high_speed.csv`
- `tables/anomaly_low_positive_price.csv`
- `tables/anomaly_low_speed.csv`
- `tables/correlation_matrix.csv`
- `tables/demand_by_airline.csv`
- `tables/demand_by_search_dow.csv`
- `tables/demand_by_search_month.csv`
- `tables/demand_by_travel_class.csv`
- `tables/demand_by_trip_type.csv`
- `tables/frequency_airline.csv`
- `tables/frequency_arrival_time.csv`
- `tables/frequency_depart_dow_name.csv`
- `tables/frequency_depart_season_name.csv`
- `tables/frequency_departure_time.csv`
- `tables/frequency_destination_type.csv`
- `tables/frequency_origin_type.csv`
- `tables/frequency_search_dow_name.csv`
- `tables/frequency_search_season_name.csv`
- `tables/frequency_travel_class.csv`
- `tables/frequency_trip_type.csv`
- `tables/heatmap_depart_dow_hour_avg_price.csv`
- `tables/missing_expected_columns.csv`
- `tables/missing_values.csv`
- `tables/model_feature_importance.csv`
- `tables/model_feature_importance_detail.csv`
- `tables/model_metrics.csv`
- `tables/numeric_describe.csv`
- `tables/overview.csv`
- `tables/pivot_airline_distance_median_price.csv`
- `tables/pivot_class_stops_median_price.csv`
- `tables/pivot_depart_month_class_avg_price.csv`
- `tables/pivot_holiday_weekend_avg_price.csv`
- `tables/pivot_search_depart_dow_count.csv`
- `tables/pivot_season_booking_median_price.csv`
- `tables/pivot_top_routes_season_passengers.csv`
- `tables/price_by_airline.csv`
- `tables/price_by_days_to_departure.csv`
- `tables/price_by_days_to_departure_bucket.csv`
- `tables/price_by_depart_dow_name.csv`
- `tables/price_by_depart_is_weekend.csv`
- `tables/price_by_depart_month.csv`
- `tables/price_by_depart_season_name.csv`
- `tables/price_by_depart_time_bucket.csv`
- `tables/price_by_destination_type.csv`
- `tables/price_by_distance_bucket.csv`
- `tables/price_by_is_direct.csv`
- `tables/price_by_is_holiday_depart.csv`
- `tables/price_by_origin_type.csv`
- `tables/price_by_price_segment.csv`
- `tables/price_by_route_type.csv`
- `tables/price_by_search_is_weekend.csv`
- `tables/price_by_stop_bucket.csv`
- `tables/price_by_stops.csv`
- `tables/price_by_travel_class.csv`
- `tables/price_by_trip_type.csv`
- `tables/price_metrics.csv`
- `tables/quality_anomalies.csv`
- `tables/statistical_tests.csv`
- `tables/top_routes_by_passengers.csv`
- `tables/top_routes_by_price_per_km.csv`
- `tables/top_routes_by_revenue.csv`

## Графіки

- `charts/price_histogram.png`
- `charts/log_price_histogram.png`
- `charts/median_price_by_days_to_departure.png`
- `charts/median_price_by_travel_class.png`
- `charts/median_price_by_stops.png`
- `charts/median_price_by_season.png`
- `charts/passengers_by_airline.png`
- `charts/top_routes_by_passengers.png`
- `charts/distance_vs_price.png`
- `charts/heatmap_depart_dow_hour_avg_price.png`
- `charts/heatmap_season_booking_median_price.png`
