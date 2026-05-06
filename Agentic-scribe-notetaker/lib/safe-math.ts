/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

type MathVariables = Record<string, number>;

type NumberToken = {
  type: 'number';
  value: number;
};

type IdentifierToken = {
  type: 'identifier';
  value: string;
};

type OperatorToken = {
  type: 'operator';
  value: '+' | '-' | '*' | '/' | '^';
};

type ParenToken = {
  type: 'paren';
  value: '(' | ')';
};

type CommaToken = {
  type: 'comma';
};

type EndToken = {
  type: 'end';
};

type Token =
  | NumberToken
  | IdentifierToken
  | OperatorToken
  | ParenToken
  | CommaToken
  | EndToken;

type MathFunction = {
  minArgs: number;
  maxArgs: number;
  evaluate: (...args: number[]) => number;
};

const MAX_EXPRESSION_LENGTH = 256;

const FUNCTIONS: Record<string, MathFunction> = {
  abs: { minArgs: 1, maxArgs: 1, evaluate: Math.abs },
  acos: { minArgs: 1, maxArgs: 1, evaluate: Math.acos },
  asin: { minArgs: 1, maxArgs: 1, evaluate: Math.asin },
  atan: { minArgs: 1, maxArgs: 1, evaluate: Math.atan },
  ceil: { minArgs: 1, maxArgs: 1, evaluate: Math.ceil },
  cos: { minArgs: 1, maxArgs: 1, evaluate: Math.cos },
  exp: { minArgs: 1, maxArgs: 1, evaluate: Math.exp },
  floor: { minArgs: 1, maxArgs: 1, evaluate: Math.floor },
  ln: { minArgs: 1, maxArgs: 1, evaluate: Math.log },
  log: { minArgs: 1, maxArgs: 1, evaluate: Math.log },
  log10: { minArgs: 1, maxArgs: 1, evaluate: Math.log10 },
  max: { minArgs: 1, maxArgs: Infinity, evaluate: Math.max },
  min: { minArgs: 1, maxArgs: Infinity, evaluate: Math.min },
  pow: { minArgs: 2, maxArgs: 2, evaluate: Math.pow },
  round: { minArgs: 1, maxArgs: 1, evaluate: Math.round },
  sin: { minArgs: 1, maxArgs: 1, evaluate: Math.sin },
  sqrt: { minArgs: 1, maxArgs: 1, evaluate: Math.sqrt },
  tan: { minArgs: 1, maxArgs: 1, evaluate: Math.tan },
};

const CONSTANTS: Record<string, number> = {
  e: Math.E,
  pi: Math.PI,
};

const normalizeExpression = (expression: string): string => {
  return expression
    .replace(/\bMath\./gi, '')
    .replace(/π/g, 'pi')
    .replace(/[−–—]/g, '-')
    .replace(/×/g, '*')
    .replace(/÷/g, '/')
    .trim();
};

const isAlpha = (char: string): boolean => /[A-Za-z_]/.test(char);
const isAlphaNumeric = (char: string): boolean => /[A-Za-z0-9_]/.test(char);
const isDigit = (char: string): boolean => /[0-9]/.test(char);

class MathExpressionParser {
  private readonly source: string;
  private readonly variables: MathVariables;
  private index = 0;
  private current: Token;

  constructor(source: string, variables: MathVariables) {
    this.source = normalizeExpression(source);
    this.variables = Object.fromEntries(
      Object.entries(variables).map(([key, value]) => [key.toLowerCase(), value]),
    );
    this.current = this.readToken();
  }

  parse(): number {
    const value = this.parseAdditive();
    if (this.current.type !== 'end') {
      throw new Error('Unexpected trailing input');
    }
    return value;
  }

  private parseAdditive(): number {
    let value = this.parseMultiplicative();

    while (
      this.current.type === 'operator' &&
      (this.current.value === '+' || this.current.value === '-')
    ) {
      const operator = this.current.value;
      this.advance();
      const right = this.parseMultiplicative();
      value = operator === '+' ? value + right : value - right;
    }

    return value;
  }

  private parseMultiplicative(): number {
    let value = this.parseUnary();

    while (true) {
      if (
        this.current.type === 'operator' &&
        (this.current.value === '*' || this.current.value === '/')
      ) {
        const operator = this.current.value;
        this.advance();
        const right = this.parseUnary();
        value = operator === '*' ? value * right : value / right;
        continue;
      }

      if (this.startsImplicitFactor()) {
        value *= this.parseUnary();
        continue;
      }

      break;
    }

    return value;
  }

  private parsePower(): number {
    const value = this.parsePrimary();

    if (this.current.type === 'operator' && this.current.value === '^') {
      this.advance();
      return Math.pow(value, this.parseUnary());
    }

    return value;
  }

  private parseUnary(): number {
    if (this.current.type === 'operator' && this.current.value === '+') {
      this.advance();
      return this.parseUnary();
    }

    if (this.current.type === 'operator' && this.current.value === '-') {
      this.advance();
      return -this.parseUnary();
    }

    return this.parsePower();
  }

  private parsePrimary(): number {
    if (this.current.type === 'number') {
      const value = this.current.value;
      this.advance();
      return value;
    }

    if (this.current.type === 'identifier') {
      return this.parseIdentifier();
    }

    if (this.current.type === 'paren' && this.current.value === '(') {
      this.advance();
      const value = this.parseAdditive();
      this.expectClosingParen();
      return value;
    }

    throw new Error('Expected number, variable, function, or parenthesized expression');
  }

  private parseIdentifier(): number {
    if (this.current.type !== 'identifier') {
      throw new Error('Expected identifier');
    }

    const name = this.current.value.toLowerCase();
    this.advance();

    if (FUNCTIONS[name]) {
      const token = this.current as Token;
      if (!(token.type === 'paren' && token.value === '(')) {
        throw new Error(`Function ${name} requires parentheses`);
      }

      return this.parseFunctionCall(name);
    }

    if (Object.prototype.hasOwnProperty.call(CONSTANTS, name)) {
      return CONSTANTS[name];
    }

    if (Object.prototype.hasOwnProperty.call(this.variables, name)) {
      const value = this.variables[name];
      if (Number.isFinite(value)) return value;
    }

    throw new Error(`Unknown identifier ${name}`);
  }

  private parseFunctionCall(name: string): number {
    const fn = FUNCTIONS[name];
    const args: number[] = [];

    this.advance();
    if (this.current.type === 'paren' && this.current.value === ')') {
      this.advance();
    } else {
      while (true) {
        args.push(this.parseAdditive());

        if (this.current.type === 'comma') {
          this.advance();
          continue;
        }

        this.expectClosingParen();
        break;
      }
    }

    if (args.length < fn.minArgs || args.length > fn.maxArgs) {
      throw new Error(`Invalid argument count for ${name}`);
    }

    return fn.evaluate(...args);
  }

  private startsImplicitFactor(): boolean {
    return (
      this.current.type === 'number' ||
      this.current.type === 'identifier' ||
      (this.current.type === 'paren' && this.current.value === '(')
    );
  }

  private expectClosingParen() {
    if (!(this.current.type === 'paren' && this.current.value === ')')) {
      throw new Error('Expected closing parenthesis');
    }
    this.advance();
  }

  private advance() {
    this.current = this.readToken();
  }

  private readToken(): Token {
    this.skipWhitespace();

    if (this.index >= this.source.length) {
      return { type: 'end' };
    }

    const char = this.source[this.index];

    if (isDigit(char) || char === '.') {
      return this.readNumber();
    }

    if (isAlpha(char)) {
      return this.readIdentifier();
    }

    if (char === '*' && this.source[this.index + 1] === '*') {
      this.index += 2;
      return { type: 'operator', value: '^' };
    }

    if (char === '+' || char === '-' || char === '*' || char === '/' || char === '^') {
      this.index += 1;
      return { type: 'operator', value: char };
    }

    if (char === '(' || char === ')') {
      this.index += 1;
      return { type: 'paren', value: char };
    }

    if (char === ',') {
      this.index += 1;
      return { type: 'comma' };
    }

    throw new Error(`Unsupported character ${char}`);
  }

  private readNumber(): NumberToken {
    const start = this.index;
    let hasDigit = false;

    while (isDigit(this.source[this.index] || '')) {
      this.index += 1;
      hasDigit = true;
    }

    if (this.source[this.index] === '.') {
      this.index += 1;
      while (isDigit(this.source[this.index] || '')) {
        this.index += 1;
        hasDigit = true;
      }
    }

    if (!hasDigit) {
      throw new Error('Invalid number');
    }

    if (this.source[this.index]?.toLowerCase() === 'e') {
      const exponentStart = this.index;
      this.index += 1;

      if (this.source[this.index] === '+' || this.source[this.index] === '-') {
        this.index += 1;
      }

      let hasExponentDigit = false;
      while (isDigit(this.source[this.index] || '')) {
        this.index += 1;
        hasExponentDigit = true;
      }

      if (!hasExponentDigit) {
        this.index = exponentStart;
      }
    }

    const value = Number(this.source.slice(start, this.index));
    if (!Number.isFinite(value)) {
      throw new Error('Invalid number');
    }

    return { type: 'number', value };
  }

  private readIdentifier(): IdentifierToken {
    const start = this.index;
    this.index += 1;

    while (isAlphaNumeric(this.source[this.index] || '')) {
      this.index += 1;
    }

    return {
      type: 'identifier',
      value: this.source.slice(start, this.index),
    };
  }

  private skipWhitespace() {
    while (/\s/.test(this.source[this.index] || '')) {
      this.index += 1;
    }
  }
}

export const evaluateMathExpression = (
  expression: string,
  variables: MathVariables = {},
): number | null => {
  if (!expression || expression.length > MAX_EXPRESSION_LENGTH) return null;

  try {
    const result = new MathExpressionParser(expression, variables).parse();
    return Number.isFinite(result) ? result : null;
  } catch {
    return null;
  }
};
