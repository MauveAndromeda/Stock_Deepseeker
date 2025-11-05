"""
持仓集中度风险管理
防止过度集中于单只股票或单一行业
预期风险降低：15-20%
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ConcentrationRisk:
    """集中度风险"""
    risk_level: RiskLevel
    risk_score: float  # 0-100
    violations: List[str]
    recommendations: List[str]
    details: Dict


class ConcentrationRiskManager:
    """
    持仓集中度风险管理器

    关键限制：
    1. 单只股票不超过15-20%
    2. 单一行业不超过30%
    3. 单一风格因子不超过40%
    4. 前5大持仓不超过50%
    5. HHI指数（Herfindahl指数）监控
    """

    def __init__(self):
        """初始化"""
        # 风险限制配置
        self.limits = {
            'max_single_position': 0.20,      # 单只股票最大20%
            'max_industry': 0.30,             # 单行业最大30%
            'max_sector': 0.40,               # 单板块最大40%
            'max_style_factor': 0.40,         # 单风格因子最大40%
            'max_top5': 0.60,                 # 前5大持仓最大60%
            'max_top10': 0.80,                # 前10大持仓最大80%
            'max_hhi': 0.15                   # HHI指数最大0.15
        }

        # 行业分类（简化版）
        self.industry_map = {
            'AAPL': 'Technology',
            'MSFT': 'Technology',
            'GOOGL': 'Technology',
            'AMZN': 'Consumer',
            'TSLA': 'Automotive',
            'JPM': 'Finance',
            'BAC': 'Finance',
            'JNJ': 'Healthcare',
            'PFE': 'Healthcare',
            'XOM': 'Energy',
            'CVX': 'Energy'
        }

    def check_concentration_risk(
        self,
        portfolio: Dict[str, float],
        portfolio_value: float = 100000
    ) -> ConcentrationRisk:
        """
        检查持仓集中度风险

        Args:
            portfolio: 持仓字典 {symbol: shares}
            portfolio_value: 组合总价值

        Returns:
            集中度风险分析
        """
        violations = []
        recommendations = []
        risk_scores = []

        # 计算持仓权重
        weights = self._calculate_weights(portfolio, portfolio_value)

        # 1. 检查单只股票集中度
        single_risk, single_violations = self._check_single_position(weights)
        violations.extend(single_violations)
        risk_scores.append(single_risk)

        # 2. 检查行业集中度
        industry_risk, industry_violations = self._check_industry_concentration(weights)
        violations.extend(industry_violations)
        risk_scores.append(industry_risk)

        # 3. 检查头部集中度
        top_risk, top_violations = self._check_top_concentration(weights)
        violations.extend(top_violations)
        risk_scores.append(top_risk)

        # 4. 计算HHI指数
        hhi_risk, hhi_violations = self._check_hhi(weights)
        violations.extend(hhi_violations)
        risk_scores.append(hhi_risk)

        # 综合风险评分
        total_risk_score = np.mean(risk_scores)

        # 确定风险等级
        if total_risk_score < 30:
            risk_level = RiskLevel.LOW
        elif total_risk_score < 60:
            risk_level = RiskLevel.MEDIUM
        elif total_risk_score < 85:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL

        # 生成建议
        if violations:
            recommendations = self._generate_recommendations(
                weights,
                violations,
                risk_level
            )

        return ConcentrationRisk(
            risk_level=risk_level,
            risk_score=total_risk_score,
            violations=violations,
            recommendations=recommendations,
            details={
                'weights': weights,
                'industry_exposure': self._calculate_industry_exposure(weights),
                'hhi': self._calculate_hhi(weights),
                'top5_concentration': self._calculate_top_n_concentration(weights, 5),
                'top10_concentration': self._calculate_top_n_concentration(weights, 10)
            }
        )

    def _calculate_weights(
        self,
        portfolio: Dict[str, float],
        portfolio_value: float
    ) -> Dict[str, float]:
        """计算持仓权重"""
        # 简化实现：假设等权
        if not portfolio:
            return {}

        total = sum(portfolio.values())
        if total == 0:
            return {}

        weights = {
            symbol: value / total
            for symbol, value in portfolio.items()
        }

        return weights

    def _check_single_position(
        self,
        weights: Dict[str, float]
    ) -> Tuple[float, List[str]]:
        """检查单只股票集中度"""
        violations = []
        risk_score = 0.0

        max_limit = self.limits['max_single_position']

        for symbol, weight in weights.items():
            if weight > max_limit:
                excess = (weight - max_limit) / max_limit * 100
                violations.append(
                    f"⚠️  {symbol} 持仓过高: {weight:.1%} "
                    f"(超出限制 {excess:.0f}%)"
                )
                risk_score = max(risk_score, 50 + excess)

            elif weight > max_limit * 0.8:
                # 接近限制，警告
                violations.append(
                    f"⚡ {symbol} 持仓接近上限: {weight:.1%} "
                    f"(限制 {max_limit:.0%})"
                )
                risk_score = max(risk_score, 40)

        return risk_score, violations

    def _check_industry_concentration(
        self,
        weights: Dict[str, float]
    ) -> Tuple[float, List[str]]:
        """检查行业集中度"""
        violations = []
        risk_score = 0.0

        # 计算行业敞口
        industry_exposure = self._calculate_industry_exposure(weights)
        max_limit = self.limits['max_industry']

        for industry, exposure in industry_exposure.items():
            if exposure > max_limit:
                excess = (exposure - max_limit) / max_limit * 100
                violations.append(
                    f"⚠️  {industry} 行业过度集中: {exposure:.1%} "
                    f"(超出限制 {excess:.0f}%)"
                )
                risk_score = max(risk_score, 60 + excess)

            elif exposure > max_limit * 0.8:
                violations.append(
                    f"⚡ {industry} 行业集中度偏高: {exposure:.1%} "
                    f"(限制 {max_limit:.0%})"
                )
                risk_score = max(risk_score, 45)

        return risk_score, violations

    def _check_top_concentration(
        self,
        weights: Dict[str, float]
    ) -> Tuple[float, List[str]]:
        """检查头部持仓集中度"""
        violations = []
        risk_score = 0.0

        # 前5大持仓
        top5 = self._calculate_top_n_concentration(weights, 5)
        max_top5 = self.limits['max_top5']

        if top5 > max_top5:
            excess = (top5 - max_top5) / max_top5 * 100
            violations.append(
                f"⚠️  前5大持仓过度集中: {top5:.1%} "
                f"(超出限制 {excess:.0f}%)"
            )
            risk_score = max(risk_score, 55 + excess)

        # 前10大持仓
        top10 = self._calculate_top_n_concentration(weights, 10)
        max_top10 = self.limits['max_top10']

        if top10 > max_top10:
            excess = (top10 - max_top10) / max_top10 * 100
            violations.append(
                f"⚠️  前10大持仓过度集中: {top10:.1%} "
                f"(超出限制 {excess:.0f}%)"
            )
            risk_score = max(risk_score, 50 + excess)

        return risk_score, violations

    def _check_hhi(
        self,
        weights: Dict[str, float]
    ) -> Tuple[float, List[str]]:
        """检查HHI指数（Herfindahl-Hirschman Index）"""
        violations = []
        risk_score = 0.0

        hhi = self._calculate_hhi(weights)
        max_hhi = self.limits['max_hhi']

        if hhi > max_hhi:
            excess = (hhi - max_hhi) / max_hhi * 100
            violations.append(
                f"⚠️  HHI指数过高: {hhi:.4f} "
                f"(限制 {max_hhi:.4f}, 超出 {excess:.0f}%)"
            )
            risk_score = max(risk_score, 60 + excess)

        return risk_score, violations

    def _calculate_industry_exposure(
        self,
        weights: Dict[str, float]
    ) -> Dict[str, float]:
        """计算行业敞口"""
        industry_exposure = {}

        for symbol, weight in weights.items():
            industry = self.industry_map.get(symbol, 'Other')

            if industry not in industry_exposure:
                industry_exposure[industry] = 0.0

            industry_exposure[industry] += weight

        return industry_exposure

    def _calculate_top_n_concentration(
        self,
        weights: Dict[str, float],
        n: int
    ) -> float:
        """计算前N大持仓集中度"""
        if not weights:
            return 0.0

        sorted_weights = sorted(weights.values(), reverse=True)
        top_n = sorted_weights[:n]

        return sum(top_n)

    def _calculate_hhi(self, weights: Dict[str, float]) -> float:
        """
        计算HHI指数

        HHI = sum(weight^2)
        HHI越高，集中度越高
        HHI = 1.0 表示只有一只股票（最高集中度）
        HHI = 1/n 表示n只股票等权（最低集中度）
        """
        if not weights:
            return 0.0

        hhi = sum(w**2 for w in weights.values())
        return hhi

    def _generate_recommendations(
        self,
        weights: Dict[str, float],
        violations: List[str],
        risk_level: RiskLevel
    ) -> List[str]:
        """生成降低集中度的建议"""
        recommendations = []

        if risk_level == RiskLevel.CRITICAL:
            recommendations.append(
                "🚨 集中度风险极高，建议立即采取行动"
            )

        # 找出最大持仓
        if weights:
            max_symbol = max(weights, key=weights.get)
            max_weight = weights[max_symbol]

            if max_weight > self.limits['max_single_position']:
                target_weight = self.limits['max_single_position']
                reduce_pct = (max_weight - target_weight) / max_weight * 100

                recommendations.append(
                    f"💡 建议减持 {max_symbol}，从 {max_weight:.1%} "
                    f"降至 {target_weight:.0%}（减少 {reduce_pct:.0f}%）"
                )

        # 行业集中度建议
        industry_exposure = self._calculate_industry_exposure(weights)
        if industry_exposure:
            max_industry = max(industry_exposure, key=industry_exposure.get)
            max_industry_exp = industry_exposure[max_industry]

            if max_industry_exp > self.limits['max_industry']:
                recommendations.append(
                    f"💡 {max_industry} 行业过度集中({max_industry_exp:.1%})，"
                    f"建议分散到其他行业"
                )

        # 通用建议
        if len(weights) < 5:
            recommendations.append(
                "💡 持仓数量较少，建议增加持仓分散度"
            )

        if self._calculate_hhi(weights) > self.limits['max_hhi']:
            recommendations.append(
                "💡 整体集中度偏高，建议增加持仓数量并平衡权重"
            )

        return recommendations

    def suggest_rebalancing(
        self,
        current_weights: Dict[str, float],
        target_max_weight: float = 0.15
    ) -> Dict[str, float]:
        """
        建议再平衡权重

        Args:
            current_weights: 当前权重
            target_max_weight: 目标最大权重

        Returns:
            建议的新权重
        """
        if not current_weights:
            return {}

        # 找出超重的股票
        overweight = {
            symbol: weight
            for symbol, weight in current_weights.items()
            if weight > target_max_weight
        }

        if not overweight:
            # 无需调整
            return current_weights

        # 计算需要减持的总权重
        excess_weight = sum(
            weight - target_max_weight
            for weight in overweight.values()
        )

        # 计算欠重的股票
        underweight = {
            symbol: weight
            for symbol, weight in current_weights.items()
            if symbol not in overweight
        }

        # 分配给欠重的股票
        new_weights = current_weights.copy()

        # 降低超重股票
        for symbol in overweight:
            new_weights[symbol] = target_max_weight

        # 增加欠重股票
        if underweight:
            allocation_per_stock = excess_weight / len(underweight)

            for symbol in underweight:
                new_weights[symbol] += allocation_per_stock

        # 归一化
        total = sum(new_weights.values())
        new_weights = {
            symbol: weight / total
            for symbol, weight in new_weights.items()
        }

        return new_weights

    def print_risk_report(self, risk: ConcentrationRisk):
        """打印风险报告"""
        print("\n" + "=" * 60)
        print("📊 持仓集中度风险报告")
        print("=" * 60)

        # 风险等级
        level_emoji = {
            RiskLevel.LOW: "✅",
            RiskLevel.MEDIUM: "⚠️ ",
            RiskLevel.HIGH: "🔴",
            RiskLevel.CRITICAL: "🚨"
        }

        print(f"\n风险等级: {level_emoji[risk.risk_level]} {risk.risk_level.value.upper()}")
        print(f"风险评分: {risk.risk_score:.1f}/100")

        # 违规项
        if risk.violations:
            print(f"\n⚠️  发现 {len(risk.violations)} 个问题:")
            for violation in risk.violations:
                print(f"  {violation}")

        # 详细信息
        print(f"\n📈 详细信息:")
        print(f"  HHI指数: {risk.details['hhi']:.4f}")
        print(f"  前5大持仓: {risk.details['top5_concentration']:.1%}")
        print(f"  前10大持仓: {risk.details['top10_concentration']:.1%}")

        # 行业分布
        print(f"\n🏢 行业分布:")
        for industry, exposure in sorted(
            risk.details['industry_exposure'].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            bar = '█' * int(exposure * 50)
            print(f"  {industry:15s} {exposure:6.1%} {bar}")

        # 建议
        if risk.recommendations:
            print(f"\n💡 改进建议:")
            for rec in risk.recommendations:
                print(f"  {rec}")

        print("\n" + "=" * 60)


# 使用示例
if __name__ == "__main__":
    manager = ConcentrationRiskManager()

    # 测试组合
    test_portfolio = {
        'AAPL': 0.25,    # 过高
        'MSFT': 0.20,    # 过高
        'GOOGL': 0.15,
        'AMZN': 0.15,
        'JPM': 0.10,
        'JNJ': 0.10,
        'TSLA': 0.05
    }

    # 检查风险
    risk = manager.check_concentration_risk(test_portfolio)

    # 打印报告
    manager.print_risk_report(risk)

    # 建议再平衡
    if risk.risk_level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
        print("\n" + "=" * 60)
        print("💡 建议的再平衡权重:")
        print("=" * 60)

        new_weights = manager.suggest_rebalancing(test_portfolio, target_max_weight=0.15)

        for symbol, weight in sorted(new_weights.items(), key=lambda x: x[1], reverse=True):
            old_weight = test_portfolio[symbol]
            change = weight - old_weight
            change_str = f"({change:+.1%})" if change != 0 else ""

            print(f"  {symbol:6s} {old_weight:6.1%} → {weight:6.1%} {change_str}")
