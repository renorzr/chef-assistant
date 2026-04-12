import React, { useState, useEffect } from "react";
import {
  BrowserRouter as Router,
  Routes,
  Route,
  useNavigate,
  useParams,
  useLocation
} from "react-router-dom";

function TabButton({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`flex-1 py-2 text-sm ${active ? "font-bold border-t-2 border-black" : "text-gray-500"}`}
    >
      {label}
    </button>
  );
}

function RecipeCard({ title, onClick, selectable, selected, onToggle }) {
  return (
    <div className="bg-white rounded-2xl shadow p-3 mb-2">
      <div onClick={onClick} className="cursor-pointer">
        <div className="bg-gray-200 h-32 rounded-xl mb-2" />
        <div className="font-semibold">{title}</div>
        <div className="text-xs text-gray-500">⏱25min ⭐简单</div>
      </div>

      {selectable && (
        <button
          onClick={onToggle}
          className={`mt-2 w-full p-2 rounded-xl text-sm ${selected ? "bg-black text-white" : "bg-gray-100"}`}
        >
          {selected ? "已选择" : "选择这道菜"}
        </button>
      )}
    </div>
  );
}

function LinkCard({ title, type, onClick }) {
  return (
    <div onClick={onClick} className="bg-gray-100 p-3 rounded-xl mb-2 cursor-pointer">
      <div className="text-xs text-gray-500">{type}</div>
      <div className="font-semibold">{title}</div>
    </div>
  );
}

function ChatMessage({ role, children }) {
  return (
    <div className={`flex ${role === "user" ? "justify-end" : "justify-start"} mb-3`}>
      <div className={`max-w-[80%] p-3 rounded-2xl ${role === "user" ? "bg-black text-white" : "bg-white"}`}>
        {children}
      </div>
    </div>
  );
}

function Home({ setSelectedMenu }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    const menus = [
      { id: "m1", title: "家庭常用菜单" },
      { id: "m2", title: "清淡晚餐菜单" }
    ];

    setMessages([
      {
        role: "assistant",
        content: "这是你常用的菜单，可以直接选择👇",
        cards: menus.map((m) => ({ ...m, type: "menu" }))
      }
    ]);
  }, []);

  const sendMessage = () => {
    if (!input) return;

    const userMsg = { role: "user", content: input };

    const aiMsg = {
      role: "assistant",
      content: "我帮你搭了一顿饭 👇",
      cards: [
        { type: "recipe", id: "r1", title: "西红柿炒蛋" },
        { type: "recipe", id: "r2", title: "紫菜蛋花汤" },
        { type: "plan", title: "今晚做饭计划" }
      ]
    };

    setMessages((prev) => [...prev, userMsg, aiMsg]);
    setInput("");
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto p-4">
        {messages.map((msg, i) => (
          <ChatMessage key={i} role={msg.role}>
            <div>
              <div className="mb-2">{msg.content}</div>

              {msg.cards && (
                <div>
                  {msg.cards.map((card, idx) => {
                    if (card.type === "recipe") {
                      return (
                        <RecipeCard
                          key={idx}
                          title={card.title}
                          onClick={() => navigate(`/recipes/${card.id}`)}
                        />
                      );
                    }

                    if (card.type === "menu") {
                      return (
                        <LinkCard
                          key={idx}
                          title={card.title}
                          type="菜单"
                          onClick={() => {
                            setSelectedMenu(card);
                            navigate(`/menus/${card.id}`);
                          }}
                        />
                      );
                    }

                    return (
                      <LinkCard
                        key={idx}
                        title={card.title}
                        type={card.type}
                        onClick={() => navigate("/plan")}
                      />
                    );
                  })}
                </div>
              )}
            </div>
          </ChatMessage>
        ))}
      </div>

      <div className="p-3 border-t bg-white flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="输入你的需求..."
          className="flex-1 p-2 bg-gray-100 rounded-xl"
        />
        <button onClick={sendMessage} className="px-4 bg-black text-white rounded-xl">
          发送
        </button>
      </div>
    </div>
  );
}

function MenuDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [selected, setSelected] = useState({});

  const dishes = [
    { id: "r1", title: "西红柿炒蛋" },
    { id: "r2", title: "紫菜蛋花汤" },
    { id: "r3", title: "蒜蓉青菜" }
  ];

  const toggle = (rid) => {
    setSelected((prev) => ({ ...prev, [rid]: !prev[rid] }));
  };

  const selectedCount = Object.values(selected).filter(Boolean).length;

  return (
    <div className="p-4">
      <h1 className="font-bold text-lg mb-3">菜单 {id}</h1>

      {dishes.map((d) => (
        <RecipeCard
          key={d.id}
          title={d.title}
          selectable
          selected={!!selected[d.id]}
          onToggle={() => toggle(d.id)}
          onClick={() => navigate(`/recipes/${d.id}`)}
        />
      ))}

      <button
        disabled={selectedCount === 0}
        onClick={() => navigate("/plan")}
        className="w-full mt-4 p-3 rounded-xl bg-black text-white disabled:opacity-30"
      >
        去做这 {selectedCount} 道菜
      </button>
    </div>
  );
}

function RecipesList() {
  const navigate = useNavigate();

  return (
    <div className="p-4">
      <input className="w-full p-2 bg-gray-100 rounded-xl mb-3" placeholder="搜索菜谱" />
      <RecipeCard title="清淡鸡汤" onClick={() => navigate("/recipes/r100")} />
    </div>
  );
}

function RecipeDetail() {
  const { id } = useParams();

  return (
    <div className="p-4">
      <div className="bg-gray-200 h-48 rounded-xl mb-3" />
      <h1 className="font-bold text-lg mb-2">菜谱 {id}</h1>
      <div className="text-sm text-gray-500 mb-3">⏱25min ⭐简单</div>
      <div>步骤内容...</div>
    </div>
  );
}

function Plan() {
  const navigate = useNavigate();

  const dishes = [
    { id: "r1", title: "西红柿炒蛋" },
    { id: "r2", title: "紫菜蛋花汤" }
  ];

  return (
    <div className="p-4">
      <h1 className="font-bold mb-3">今日晚餐</h1>

      {dishes.map((d) => (
        <RecipeCard key={d.id} title={d.title} onClick={() => navigate(`/recipes/${d.id}`)} />
      ))}
    </div>
  );
}

function Layout() {
  const location = useLocation();
  const navigate = useNavigate();
  const [selectedMenu, setSelectedMenu] = useState(null);

  return (
    <div className="max-w-sm mx-auto h-screen flex flex-col bg-gray-50">
      <div className="flex-1 overflow-auto">
        <Routes>
          <Route path="/" element={<Home setSelectedMenu={setSelectedMenu} />} />
          <Route path="/recipes" element={<RecipesList />} />
          <Route path="/recipes/:id" element={<RecipeDetail />} />
          <Route path="/menus/:id" element={<MenuDetail />} />
          <Route path="/plan" element={<Plan />} />
        </Routes>
      </div>

      <div className="flex border-t bg-white">
        <TabButton label="对话" active={location.pathname === "/"} onClick={() => navigate("/")} />
        <TabButton
          label="菜谱"
          active={location.pathname.startsWith("/recipes")}
          onClick={() => navigate("/recipes")}
        />
        <TabButton
          label="菜单"
          active={location.pathname.startsWith("/menus")}
          onClick={() => navigate("/menus/m1")}
        />
        <TabButton label="计划" active={location.pathname === "/plan"} onClick={() => navigate("/plan")} />
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Router>
      <Layout />
    </Router>
  );
}

