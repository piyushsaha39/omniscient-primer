import google.generativeai as genai
from typing import Any, List

class GeminiService:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite",
            #tools=[{"google_search_retrieval": {}}]
        )

    def _get_model(self, system_prompt: str = "") -> genai.GenerativeModel:
        if system_prompt:
            return genai.GenerativeModel(
                model_name="gemini-3.1-flash-lite",
                #tools=[{"google_search_retrieval": {}}],
                system_instruction=system_prompt
            )
        return self.model

    def generate_text(self, prompt: str, system_prompt: str = "") -> str:
        model = self._get_model(system_prompt)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.4)
        )
        return response.text

    def generate_json(self, prompt: str, system_prompt: str = "") -> str:
        model = self._get_model(system_prompt)
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.3,
                response_mime_type="application/json"
            )
        )
        return response.text

    def generate_with_tools(self, prompt: str, tools: List[Any], system_prompt: str = "") -> Any:
        model = genai.GenerativeModel(
            model_name="gemini-3.1-flash-lite",
            tools=tools,
            system_instruction=system_prompt if system_prompt else None
        )
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.3)
        )
        return response
