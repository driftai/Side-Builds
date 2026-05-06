import { GoogleGenAI, Type } from '@google/genai';

const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY,
});

const controlLightFunctionDeclaration = {
  name: 'controlLight',
  description: 'Set the brightness and color temperature of a room light.',
  parameters: {
    type: Type.OBJECT,
    properties: {
      brightness: { type: Type.NUMBER },
      colorTemperature: { type: Type.STRING },
    },
    required: ['brightness', 'colorTemperature'],
  },
};

async function test() {
  try {
    const history: any[] = [
      { role: 'user', parts: [{ text: "Dim the lights to 20%" }] }
    ];

    console.log("Sending message...");
    const response = await ai.models.generateContent({
      model: 'gemini-3.1-flash-lite-preview',
      contents: history,
      config: {
        tools: [{ functionDeclarations: [controlLightFunctionDeclaration] }],
      }
    });

    console.log("Response content parts:", JSON.stringify(response.candidates?.[0]?.content?.parts, null, 2));

    if (response.functionCalls) {
      history.push(response.candidates![0].content);

      const parts = response.functionCalls.map(call => ({
        functionResponse: {
          id: call.id,
          name: call.name,
          response: { status: 'success' }
        }
      }));
      
      history.push({ role: 'user', parts });

      console.log("Sending function response...");
      const response2 = await ai.models.generateContent({
        model: 'gemini-3.1-flash-lite-preview',
        contents: history,
        config: {
          tools: [{ functionDeclarations: [controlLightFunctionDeclaration] }],
        }
      });
      console.log("Final response:", response2.text);
    }
  } catch (e) {
    console.error("Error:", e);
  }
}

test();
