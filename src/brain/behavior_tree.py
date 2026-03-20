"""
轻量级行为树框架
实现 Selector / Sequence / Condition / Action 四种核心节点
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Optional
from loguru import logger


class NodeStatus(Enum):
    """行为树节点执行状态"""
    SUCCESS = "success"
    FAILURE = "failure"
    RUNNING = "running"


class BTNode(ABC):
    """行为树节点基类"""

    def __init__(self, name: str = ""):
        self.name = name or self.__class__.__name__

    @abstractmethod
    def tick(self) -> NodeStatus:
        """执行一次节点逻辑"""
        ...

    def reset(self) -> None:
        """重置节点状态"""
        pass


class Selector(BTNode):
    """
    选择节点（或节点）：依次尝试子节点，任一成功则成功
    用途：优先级决策（如"先检查是否卡住，再执行主任务"）
    """

    def __init__(self, name: str, children: list[BTNode]):
        super().__init__(name)
        self.children = children

    def tick(self) -> NodeStatus:
        for child in self.children:
            status = child.tick()
            if status == NodeStatus.SUCCESS:
                return NodeStatus.SUCCESS
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING
        return NodeStatus.FAILURE

    def reset(self) -> None:
        for child in self.children:
            child.reset()


class Sequence(BTNode):
    """
    序列节点（与节点）：依次执行子节点，全部成功才成功
    用途：执行有序步骤（如"导航→战斗→拾取"）
    """

    def __init__(self, name: str, children: list[BTNode]):
        super().__init__(name)
        self.children = children
        self._current_index = 0

    def tick(self) -> NodeStatus:
        while self._current_index < len(self.children):
            child = self.children[self._current_index]
            status = child.tick()

            if status == NodeStatus.FAILURE:
                self._current_index = 0
                return NodeStatus.FAILURE
            if status == NodeStatus.RUNNING:
                return NodeStatus.RUNNING

            # SUCCESS → 继续下一个
            self._current_index += 1

        # 所有子节点成功
        self._current_index = 0
        return NodeStatus.SUCCESS

    def reset(self) -> None:
        self._current_index = 0
        for child in self.children:
            child.reset()


class Condition(BTNode):
    """
    条件节点：根据回调函数结果返回 SUCCESS/FAILURE
    用途：检查状态（如"是否有敌人"、"钥匙是否齐全"）
    """

    def __init__(self, name: str, check_fn: callable):
        """
        Args:
            name: 节点名称
            check_fn: 条件检查函数，返回bool
        """
        super().__init__(name)
        self._check_fn = check_fn

    def tick(self) -> NodeStatus:
        try:
            result = self._check_fn()
            return NodeStatus.SUCCESS if result else NodeStatus.FAILURE
        except Exception as e:
            logger.error("条件节点 '{}' 执行出错: {}", self.name, e)
            return NodeStatus.FAILURE


class Action(BTNode):
    """
    动作节点：执行一个动作回调，根据返回值判断状态
    用途：执行具体操作（如"释放技能"、"开箱"）
    """

    def __init__(self, name: str, action_fn: callable):
        """
        Args:
            name: 节点名称
            action_fn: 动作函数，返回 NodeStatus 或 bool
                       (True → SUCCESS, False → FAILURE, None → RUNNING)
        """
        super().__init__(name)
        self._action_fn = action_fn

    def tick(self) -> NodeStatus:
        try:
            result = self._action_fn()
            if isinstance(result, NodeStatus):
                return result
            if result is True:
                return NodeStatus.SUCCESS
            if result is False:
                return NodeStatus.FAILURE
            return NodeStatus.RUNNING
        except Exception as e:
            logger.error("动作节点 '{}' 执行出错: {}", self.name, e)
            return NodeStatus.FAILURE


class RepeatUntilSuccess(BTNode):
    """
    重复执行子节点直到成功（用于战斗循环）
    """

    def __init__(self, name: str, child: BTNode, max_attempts: int = 100):
        super().__init__(name)
        self._child = child
        self._max_attempts = max_attempts
        self._attempts = 0

    def tick(self) -> NodeStatus:
        if self._attempts >= self._max_attempts:
            self._attempts = 0
            return NodeStatus.FAILURE

        status = self._child.tick()
        self._attempts += 1

        if status == NodeStatus.SUCCESS:
            self._attempts = 0
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING

    def reset(self) -> None:
        self._attempts = 0
        self._child.reset()


class Inverter(BTNode):
    """
    取反节点：将子节点的SUCCESS变为FAILURE，反之亦然
    """

    def __init__(self, name: str, child: BTNode):
        super().__init__(name)
        self._child = child

    def tick(self) -> NodeStatus:
        status = self._child.tick()
        if status == NodeStatus.SUCCESS:
            return NodeStatus.FAILURE
        if status == NodeStatus.FAILURE:
            return NodeStatus.SUCCESS
        return NodeStatus.RUNNING

    def reset(self) -> None:
        self._child.reset()
