#!/usr/bin/env python
"""
Bezier Mouse Movement Manager
베지에 곡선을 이용한 자연스러운 마우스 움직임 구현
"""

import math
import time
import random
import logging
from typing import List, Tuple, Optional
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.remote.webelement import WebElement

logger = logging.getLogger(__name__)

class BezierMouseManager:
    """베지에 곡선을 이용한 인간적인 마우스 움직임 관리 클래스"""
    
    def __init__(self, driver):
        self.driver = driver
        self.action_chains = ActionChains(driver)
        
        # 베지에 곡선 설정
        self.curve_complexity = 3  # Control points 수
        self.overshoot_probability = 0.3  # 오버슈트 발생 확률
        self.overshoot_distance = (5, 15)  # 오버슈트 거리 범위 (px)
        self.micro_movements = True  # 미세 움직임 활성화
        
        # 속도 프로파일 설정
        self.speed_profiles = {
            'slow': {'base_duration': 1.5, 'variance': 0.8},
            'normal': {'base_duration': 0.8, 'variance': 0.4},
            'fast': {'base_duration': 0.4, 'variance': 0.2}
        }
    
    def bezier_curve(self, start: Tuple[float, float], end: Tuple[float, float], 
                    control_points: List[Tuple[float, float]], steps: int = 50) -> List[Tuple[float, float]]:
        """베지에 곡선 계산"""
        points = []
        
        for i in range(steps + 1):
            t = i / steps
            point = self._calculate_bezier_point(t, [start] + control_points + [end])
            points.append(point)
            
        return points
    
    def _calculate_bezier_point(self, t: float, control_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        """주어진 t 값에서 베지에 곡선 상의 점 계산"""
        n = len(control_points) - 1
        x, y = 0, 0
        
        for i, (px, py) in enumerate(control_points):
            coefficient = self._binomial_coefficient(n, i) * (1 - t) ** (n - i) * t ** i
            x += coefficient * px
            y += coefficient * py
            
        return (x, y)
    
    def _binomial_coefficient(self, n: int, k: int) -> int:
        """이항계수 계산"""
        if k > n - k:
            k = n - k
        result = 1
        for i in range(k):
            result = result * (n - i) // (i + 1)
        return result
    
    def _generate_control_points(self, start: Tuple[float, float], end: Tuple[float, float]) -> List[Tuple[float, float]]:
        """베지에 곡선을 위한 제어점 생성"""
        start_x, start_y = start
        end_x, end_y = end
        
        # 거리 계산
        distance = math.sqrt((end_x - start_x)**2 + (end_y - start_y)**2)
        
        control_points = []
        
        # 거리에 따른 편차 조정
        max_deviation = min(distance * 0.25, 100)  # 최대 편차는 거리의 25% 또는 100px
        
        for i in range(self.curve_complexity):
            progress = (i + 1) / (self.curve_complexity + 1)
            
            # 직선상의 점에서 시작
            mid_x = start_x + (end_x - start_x) * progress
            mid_y = start_y + (end_y - start_y) * progress
            
            # 랜덤 편차 추가
            deviation_x = random.uniform(-max_deviation, max_deviation)
            deviation_y = random.uniform(-max_deviation, max_deviation)
            
            # 인간의 손떨림 시뮬레이션 (고주파 노이즈)
            tremor_x = random.uniform(-3, 3)
            tremor_y = random.uniform(-3, 3)
            
            control_x = mid_x + deviation_x + tremor_x
            control_y = mid_y + deviation_y + tremor_y
            
            control_points.append((control_x, control_y))
        
        return control_points
    
    def _calculate_dynamic_duration(self, distance: float, speed_profile: str = 'normal') -> float:
        """거리에 따른 동적 움직임 시간 계산"""
        profile = self.speed_profiles[speed_profile]
        
        # 거리에 따른 기본 시간 (Fitts's law 근사)
        base_time = profile['base_duration'] * (1 + math.log2(distance / 10 + 1))
        
        # 랜덤 편차 추가
        variance = random.uniform(-profile['variance'], profile['variance'])
        
        return max(0.1, base_time + variance)
    
    def _add_overshoot(self, end: Tuple[float, float]) -> List[Tuple[float, float]]:
        """오버슈트 효과 추가 (인간이 목표를 살짝 지나쳤다가 돌아오는 효과)"""
        if random.random() > self.overshoot_probability:
            return []
        
        end_x, end_y = end
        
        # 오버슈트 거리와 방향
        overshoot_dist = random.uniform(*self.overshoot_distance)
        overshoot_angle = random.uniform(0, 2 * math.pi)
        
        overshoot_x = end_x + overshoot_dist * math.cos(overshoot_angle)
        overshoot_y = end_y + overshoot_dist * math.sin(overshoot_angle)
        
        # 오버슈트 후 원래 위치로 돌아오기
        return [(overshoot_x, overshoot_y), end]
    
    def _add_micro_movements(self, target: Tuple[float, float]) -> List[Tuple[float, float]]:
        """목표 지점 근처에서 미세 움직임 추가"""
        if not self.micro_movements:
            return []
        
        target_x, target_y = target
        micro_moves = []
        
        # 1-3개의 미세 움직임
        num_moves = random.randint(1, 3)
        
        for _ in range(num_moves):
            # 목표 지점 근처 1-4px 범위의 미세 움직임
            micro_x = target_x + random.uniform(-4, 4)
            micro_y = target_y + random.uniform(-4, 4)
            micro_moves.append((micro_x, micro_y))
        
        # 최종적으로 정확한 목표 지점으로
        micro_moves.append(target)
        
        return micro_moves
    
    def move_to_element_bezier(self, element: WebElement, speed_profile: str = 'normal', 
                              enable_overshoot: bool = True) -> bool:
        """베지에 곡선을 이용하여 요소로 마우스 이동"""
        try:
            # 현재 마우스 위치 (대략적으로 화면 중앙에서 시작)
            current_x = self.driver.execute_script("return window.innerWidth") // 2
            current_y = self.driver.execute_script("return window.innerHeight") // 2
            
            # 목표 요소의 위치
            element_location = element.location_once_scrolled_into_view
            element_size = element.size
            
            # 요소 중앙 계산 (약간의 랜덤 오프셋 추가)
            target_x = element_location['x'] + element_size['width'] // 2 + random.randint(-5, 5)
            target_y = element_location['y'] + element_size['height'] // 2 + random.randint(-5, 5)
            
            logger.info(f"🎯 Bezier move: ({current_x}, {current_y}) → ({target_x}, {target_y})")
            
            # 베지에 곡선 경로 생성
            start = (current_x, current_y)
            end = (target_x, target_y)
            
            control_points = self._generate_control_points(start, end)
            
            # 거리에 따른 스텝 수 조정
            distance = math.sqrt((target_x - current_x)**2 + (target_y - current_y)**2)
            steps = max(20, min(80, int(distance / 5)))  # 거리에 따라 20-80 스텝
            
            curve_points = self.bezier_curve(start, end, control_points, steps)
            
            # 움직임 시간 계산
            total_duration = self._calculate_dynamic_duration(distance, speed_profile)
            step_duration = total_duration / len(curve_points)
            
            # 베지에 곡선을 따라 마우스 이동
            for i, (x, y) in enumerate(curve_points):
                # 가속/감속 시뮬레이션 (시작과 끝이 느림)
                progress = i / len(curve_points)
                speed_multiplier = 4 * progress * (1 - progress) + 0.2  # 속도 곡선
                
                current_step_duration = step_duration / speed_multiplier
                
                try:
                    # 브라우저 좌표계로 변환하여 이동
                    self.driver.execute_script(f"""
                        var event = new MouseEvent('mousemove', {{
                            clientX: {x},
                            clientY: {y},
                            bubbles: true
                        }});
                        document.dispatchEvent(event);
                    """)
                    
                    time.sleep(max(0.001, current_step_duration))
                    
                except Exception as e:
                    logger.warning(f"⚠️ Mouse move step failed: {e}")
                    continue
            
            # 오버슈트 효과 (활성화된 경우)
            if enable_overshoot:
                overshoot_points = self._add_overshoot(end)
                for overshoot_x, overshoot_y in overshoot_points:
                    try:
                        self.driver.execute_script(f"""
                            var event = new MouseEvent('mousemove', {{
                                clientX: {overshoot_x},
                                clientY: {overshoot_y},
                                bubbles: true
                            }});
                            document.dispatchEvent(event);
                        """)
                        time.sleep(random.uniform(0.05, 0.15))
                    except:
                        pass
            
            # 미세 움직임 (목표 지점 근처)
            micro_points = self._add_micro_movements(end)
            for micro_x, micro_y in micro_points:
                try:
                    self.driver.execute_script(f"""
                        var event = new MouseEvent('mousemove', {{
                            clientX: {micro_x},
                            clientY: {micro_y},
                            bubbles: true
                        }});
                        document.dispatchEvent(event);
                    """)
                    time.sleep(random.uniform(0.02, 0.08))
                except:
                    pass
            
            # 최종적으로 ActionChains로 정확한 클릭 위치 이동
            self.action_chains.move_to_element(element).perform()
            
            # 클릭 전 아주 짧은 대기 (인간적 반응 시간)
            time.sleep(random.uniform(0.05, 0.2))
            
            logger.info(f"✅ Bezier movement completed in {total_duration:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"❌ Bezier mouse movement failed: {e}")
            # 실패 시 기본 움직임으로 폴백
            try:
                self.action_chains.move_to_element(element).perform()
                time.sleep(random.uniform(0.1, 0.3))
                return True
            except:
                return False
    
    def click_with_bezier_move(self, element: WebElement, speed_profile: str = 'normal', 
                              click_type: str = 'left') -> bool:
        """베지에 곡선 움직임 후 클릭"""
        try:
            # 베지에 곡선으로 이동
            if not self.move_to_element_bezier(element, speed_profile):
                return False
            
            # 클릭 전 미세한 대기 (인간적 반응 시간)
            time.sleep(random.uniform(0.05, 0.2))
            
            # 클릭 실행
            if click_type == 'right':
                self.action_chains.context_click(element).perform()
            else:
                element.click()
            
            logger.info(f"✅ Bezier click completed ({click_type})")
            
            # 클릭 후 미세한 대기
            time.sleep(random.uniform(0.1, 0.3))
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Bezier click failed: {e}")
            return False
    
    def hover_with_bezier_move(self, element: WebElement, hover_duration: Optional[float] = None) -> bool:
        """베지에 곡선 움직임 후 호버"""
        try:
            # 베지에 곡선으로 이동
            if not self.move_to_element_bezier(element, 'slow'):
                return False
            
            # 호버 지속 시간
            if hover_duration is None:
                hover_duration = random.uniform(0.5, 2.0)
            
            time.sleep(hover_duration)
            
            logger.info(f"✅ Bezier hover completed ({hover_duration:.1f}s)")
            return True
            
        except Exception as e:
            logger.error(f"❌ Bezier hover failed: {e}")
            return False


def get_bezier_mouse_manager(driver):
    """BezierMouseManager 인스턴스 반환"""
    return BezierMouseManager(driver) 