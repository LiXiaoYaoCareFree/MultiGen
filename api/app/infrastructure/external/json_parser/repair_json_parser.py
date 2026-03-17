import logging
from typing import Optional, Any, Union, Dict, List

import json_repair

from app.domain.external.json_parser import JSONParser

logger = logging.getLogger(__name__)


class RepairJSONParser(JSONParser):
    """基于修复逻辑的json解析器"""

    async def invoke(self, text: str, default_value: Optional[Any] = None) -> Union[Dict, List, Any]:
        """传递文本，并使用json修复库进行修复"""
        # 1.记录日志并判断text是否传递
        logger.info(f"解析json文本: {text}")
        if not text or not text.strip():
            if default_value is not None:
                return default_value
            raise ValueError("json文本为空，且无默认值")

        # 2.存在数值则使用json_repair库修复并解析
        return json_repair.repair_json(text, ensure_ascii=False, return_objects=True)
