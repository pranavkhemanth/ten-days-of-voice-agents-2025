export interface Product {
  id: string;
  name: string;
  description: string;
  price: number;
  currency: string;
  category: string;
  color: string;
  sizes?: string[];
}

export const PRODUCTS: Product[] = [
  {
    id: "mug-001",
    name: "Stoneware Coffee Mug",
    description: "Durable stoneware mug, 12oz",
    price: 800,
    currency: "INR",
    category: "mug",
    color: "white",
    sizes: [], // Mugs don't have sizes
  },
  {
    id: "hoodie-001",
    name: "Premium Black Hoodie",
    description: "Comfortable cotton hoodie",
    price: 1500,
    currency: "INR",
    category: "hoodie",
    color: "black",
    sizes: ["S", "M", "L", "XL"],
  },
  {
    id: "tshirt-001",
    name: "Classic White T-Shirt",
    description: "100% cotton, unisex fit",
    price: 900,
    currency: "INR",
    category: "tshirt",
    color: "white",
    sizes: ["S", "M", "L", "XL"],
  },
];
