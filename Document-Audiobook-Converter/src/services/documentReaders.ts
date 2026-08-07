import mammoth from 'mammoth/mammoth.browser';

export const readTextFile = async (file: File): Promise<string> => {
    const reader = new FileReader();
    return new Promise<string>((resolve, reject) => {
        reader.onload = event => resolve(event.target?.result as string);
        reader.onerror = () => reject(new Error('Failed to read text file'));
        reader.readAsText(file);
    });
};

export const readDocxFile = async (file: File): Promise<string> => {
    const arrayBuffer = await file.arrayBuffer();
    const result = await mammoth.extractRawText({ arrayBuffer });
    return result.value;
};
