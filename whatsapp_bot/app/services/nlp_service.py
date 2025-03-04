




import google.generativeai as genai

class DealerAgent:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.context = {
            "dealer_services": {
                "product_categories": [
                    "Processors (AMD Ryzen Series)",
                    "Graphics Cards (Radeon RX Series)",
                    "Motherboards",
                    "Memory",
                    "Storage"
                ],
                "support_services": [
                    "Technical Support",
                    "Warranty Claims",
                    "Product Returns",
                    "Order Status"
                ]
            }
        }
        self.conversation = self.model.start_chat(history=[
            {"role": "user", "parts": [self._create_system_prompt()]}
        ])

    def _create_system_prompt(self) -> str:
        return f"""
        You are an AMD dealer's assistant. Here are the services and products you can help with:
        Product Categories: {', '.join(self.context['dealer_services']['product_categories'])}
        Support Services: {', '.join(self.context['dealer_services']['support_services'])}
        Follow these rules:
        1. Always start with a welcome message and ask for the customer's name.
        2. Keep context of the conversation and refer back to previous information.
        3. Guide through categories before showing specific products.
        """

    async def process_message(self, message: str) -> str:
        try:
            response = await self.conversation.send_message_async(message)
            return response.text
        except Exception as e:
            return f"Error processing message: {str(e)}"