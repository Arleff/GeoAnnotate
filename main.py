import tkinter as tk
from tkinter import filedialog, colorchooser, ttk, messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
import re
from IPython.display import display, HTML

# 适配Jupyter Notebook显示
display(HTML("<style>.container { width:100% !important; }</style>"))

# 项目信息
__version__ = "1.3.5"
__description__ = "支持颜色编码输入和独立边框绘制的卫星图标注工具"

# 全局变量
current_image = None  # 当前图像
photo = None  # 显示用图像
history = []  # 历史记录

# 颜色与填充设置
fill_color = (255, 255, 0)  # 默认填充色：黄色
border_color = (0, 0, 0)    # 默认边框色：黑色
color_threshold = 30        # 颜色匹配阈值

# 边框设置
border_thickness = 1        # 边框厚度
is_drawing_border = False   # 边框绘制模式
is_annotating = False       # 填充标注模式

# 图像交互参数
zoom_factor = 1.0
canvas_offset = [0, 0]
max_zoom = 10.0
min_zoom = 0.1
is_dragging = False
last_mouse_pos = (0, 0)
original_size = (0, 0)
display_size = (0, 0)


def main():
    """主函数：创建UI并启动程序"""
    root = tk.Tk()
    root.title(f"卫星图标注工具 v{__version__}")
    root.geometry("1300x800")
    
    # 布局：左侧图像区，右侧控制区
    left_frame = ttk.Frame(root)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
    
    global canvas
    canvas = tk.Canvas(left_frame, bg="#f0f0f0")
    canvas.pack(fill=tk.BOTH, expand=True)
    
    # 绑定事件
    canvas.bind("<Configure>", on_canvas_resize)
    canvas.bind("<MouseWheel>", on_mousewheel)
    canvas.bind("<Button-4>", on_mousewheel)
    canvas.bind("<Button-5>", on_mousewheel)
    canvas.bind("<Button-1>", on_mouse_down)
    canvas.bind("<B1-Motion>", on_mouse_drag)
    canvas.bind("<ButtonRelease-1>", on_mouse_up)
    
    # 右侧控制栏
    right_frame = ttk.Frame(root, width=350)
    right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=5)
    right_frame.pack_propagate(False)
    
    create_control_panel(right_frame)
    
    root.mainloop()


def create_control_panel(parent):
    """创建右侧控制面板"""
    # 0. 状态显示（提前创建，确保所有控件都能访问）
    global status_label
    status_label = ttk.Label(parent, text="就绪 - 请上传图像", anchor=tk.W)
    status_label.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
    
    # 1. 图像操作区（上传、缩放）
    img_frame = ttk.LabelFrame(parent, text="图像操作")
    img_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Button(img_frame, text="上传图像", command=upload_image).pack(fill=tk.X, padx=5, pady=5)
    
    # 缩放控制
    zoom_frame = ttk.Frame(img_frame)
    zoom_frame.pack(fill=tk.X, padx=5, pady=5)
    ttk.Button(zoom_frame, text="放大", command=lambda: zoom(1.2)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
    ttk.Button(zoom_frame, text="缩小", command=lambda: zoom(0.8)).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
    ttk.Button(zoom_frame, text="重置视图", command=reset_view).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=2)
    
    # 2. 颜色匹配阈值（放在标注上面）
    threshold_frame = ttk.LabelFrame(parent, text="颜色匹配设置")
    threshold_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Label(threshold_frame, text="颜色匹配阈值:").pack(anchor=tk.W, padx=5)
    global threshold_label
    threshold_label = ttk.Label(threshold_frame, text=str(color_threshold))
    threshold_label.pack(anchor=tk.W, padx=5)
    ttk.Scale(
        threshold_frame, from_=0, to=100, orient=tk.HORIZONTAL,
        command=lambda v: update_threshold(int(float(v)))
    ).set(color_threshold)
    ttk.Scale(
        threshold_frame, from_=0, to=100, orient=tk.HORIZONTAL,
        command=lambda v: update_threshold(int(float(v)))
    ).pack(fill=tk.X, padx=5, pady=5)
    
    # 3. 颜色选择区
    color_frame = ttk.LabelFrame(parent, text="颜色设置")
    color_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # 填充颜色设置
    fill_frame = ttk.Frame(color_frame)
    fill_frame.pack(fill=tk.X, padx=5, pady=3)
    
    ttk.Label(fill_frame, text="填充色:").pack(side=tk.LEFT, padx=5)
    ttk.Button(fill_frame, text="选择", command=choose_fill_color).pack(side=tk.LEFT, padx=5)
    
    global fill_color_entry
    fill_color_entry = ttk.Entry(fill_frame, width=15)
    fill_color_entry.pack(side=tk.LEFT, padx=5)
    fill_color_entry.insert(0, f"rgb{fill_color}")
    
    ttk.Button(fill_frame, text="应用", command=apply_fill_color).pack(side=tk.LEFT, padx=5)
    
    global fill_color_preview
    fill_color_preview = tk.Canvas(fill_frame, width=50, height=20, bg=rgb_to_hex(fill_color))
    fill_color_preview.pack(side=tk.LEFT, padx=5)
    
    # 边框颜色设置
    border_frame = ttk.Frame(color_frame)
    border_frame.pack(fill=tk.X, padx=5, pady=3)
    
    ttk.Label(border_frame, text="边框色:").pack(side=tk.LEFT, padx=5)
    ttk.Button(border_frame, text="选择", command=choose_border_color).pack(side=tk.LEFT, padx=5)
    
    global border_color_entry
    border_color_entry = ttk.Entry(border_frame, width=15)
    border_color_entry.pack(side=tk.LEFT, padx=5)
    border_color_entry.insert(0, f"rgb{border_color}")
    
    ttk.Button(border_frame, text="应用", command=apply_border_color).pack(side=tk.LEFT, padx=5)
    
    global border_color_preview
    border_color_preview = tk.Canvas(border_frame, width=50, height=20, bg=rgb_to_hex(border_color))
    border_color_preview.pack(side=tk.LEFT, padx=5)
    
    # 4. 标注模式选择
    annotate_frame = ttk.LabelFrame(parent, text="标注模式")
    annotate_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # 边框厚度
    ttk.Label(annotate_frame, text="边框厚度 (像素):").pack(anchor=tk.W, padx=5)
    global border_thickness_slider, border_thickness_label
    border_thickness_label = ttk.Label(annotate_frame, text=str(border_thickness))
    border_thickness_label.pack(anchor=tk.W, padx=5)
    border_thickness_slider = ttk.Scale(
        annotate_frame, from_=1, to=10, orient=tk.HORIZONTAL,
        command=lambda v: update_border_thickness(int(float(v)))
    )
    border_thickness_slider.set(border_thickness)
    border_thickness_slider.pack(fill=tk.X, padx=5, pady=3)
    
    # 标注模式按钮
    global annotate_btn, border_btn
    annotate_btn = ttk.Button(annotate_frame, text="开始填充标注", command=toggle_annotate_mode)
    annotate_btn.pack(fill=tk.X, padx=5, pady=3)
    
    border_btn = ttk.Button(annotate_frame, text="开始绘制边框", command=toggle_border_mode)
    border_btn.pack(fill=tk.X, padx=5, pady=3)
    
    # 5. 操作区（保存、撤销）
    op_frame = ttk.LabelFrame(parent, text="操作")
    op_frame.pack(fill=tk.X, padx=5, pady=5)
    
    ttk.Button(op_frame, text="保存图像",  command=save_image).pack(fill=tk.X, padx=5, pady=3)
    ttk.Button(op_frame, text="撤销", command=undo).pack(fill=tk.X, padx=5, pady=3)


# 图像操作函数
def upload_image():
    """上传图像并初始化"""
    global current_image, original_size, history
    
    # 支持更多图像格式
    path = filedialog.askopenfilename(
        filetypes=[
            ("所有支持的图像", "*.png;*.jpg;*.jpeg;*.bmp;*.tiff;*.tif;*.webp;*.gif;*.ico"),
            ("PNG", "*.png"),
            ("JPG", "*.jpg;*.jpeg"),
            ("BMP", "*.bmp"),
            ("TIFF", "*.tiff;*.tif"),
            ("WebP", "*.webp"),
            ("GIF", "*.gif"),
            ("ICO", "*.ico"),
            ("所有文件", "*.*")
        ],
        title="选择图像"
    )
    if not path:
        return
    
    try:
        # 打开图像并转换为RGB模式
        current_image = Image.open(path).convert("RGB")
        original_size = (current_image.width, current_image.height)
        history = [current_image.copy()]  # 初始化历史记录
        reset_view()
        status_label.config(text=f"已加载: {path.split('/')[-1]}")
    except Exception as e:
        messagebox.showerror("错误", f"加载失败: {str(e)}")


def save_image():
    """保存当前图像"""
    if not current_image:
        messagebox.showwarning("提示", "没有图像可保存")
        return
    
    path = filedialog.asksaveasfilename(
        defaultextension=".png",
        filetypes=[
            ("PNG", "*.png"),
            ("JPG", "*.jpg"),
            ("BMP", "*.bmp"),
            ("TIFF", "*.tiff"),
            ("WebP", "*.webp"),
            ("所有文件", "*.*")
        ]
    )
    if not path:
        return
    
    try:
        # 根据文件扩展名确定保存格式
        format = path.split('.')[-1].upper()
        if format == 'JPG':
            format = 'JPEG'
        current_image.save(path, format=format)
        status_label.config(text=f"已保存至: {path}")
    except Exception as e:
        messagebox.showerror("错误", f"保存失败: {str(e)}")


def resize_image():
    """根据当前缩放因子调整图像大小"""
    global photo, display_size
    if not current_image:
        return
    
    # 计算显示尺寸
    display_size = (
        int(original_size[0] * zoom_factor),
        int(original_size[1] * zoom_factor)
    )
    
    # 缩放图像
    resized = current_image.resize(display_size, Image.Resampling.LANCZOS)
    photo = ImageTk.PhotoImage(resized)
    
    # 刷新画布
    canvas.delete("all")
    canvas.create_image(canvas_offset[0], canvas_offset[1], anchor=tk.NW, image=photo)


# 交互事件处理
def on_canvas_resize(event):
    """画布大小改变时重绘"""
    if current_image:
        resize_image()


def zoom(factor):
    """缩放图像"""
    global zoom_factor
    if not current_image:
        return
    
    zoom_factor = max(min(zoom_factor * factor, max_zoom), min_zoom)
    resize_image()
    status_label.config(text=f"缩放: {zoom_factor:.1f}x")


def reset_view():
    """重置视图"""
    global zoom_factor, canvas_offset
    zoom_factor = 1.0
    canvas_offset = [0, 0]
    resize_image()


def on_mousewheel(event):
    """鼠标滚轮缩放"""
    if event.delta > 0 or event.num == 4:
        zoom(1.1)  # 放大
    else:
        zoom(0.9)  # 缩小


def on_mouse_down(event):
    """鼠标按下事件"""
    global is_dragging, last_mouse_pos
    
    if not current_image:
        return
    
    if is_annotating:
        # 填充模式 - 处理填充
        handle_fill_annotation(event)
    elif is_drawing_border:
        # 边框模式 - 处理边框绘制
        handle_border_drawing(event)
    else:
        # 浏览模式 - 开始拖动
        is_dragging = True
        last_mouse_pos = (event.x, event.y)
        canvas.config(cursor="fleur")


def on_mouse_drag(event):
    """鼠标拖动事件"""
    global last_mouse_pos  # 添加这一行解决UnboundLocalError
    if is_dragging and not is_annotating and not is_drawing_border:
        global canvas_offset
        dx = event.x - last_mouse_pos[0]
        dy = event.y - last_mouse_pos[1]
        canvas_offset[0] += dx
        canvas_offset[1] += dy
        last_mouse_pos = (event.x, event.y)
        resize_image()


def on_mouse_up(event):
    """鼠标释放事件"""
    global is_dragging
    is_dragging = False
    canvas.config(cursor="arrow")


# 颜色处理工具
def rgb_to_hex(rgb):
    """RGB转十六进制颜色码"""
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def hex_to_rgb(hex_str):
    """十六进制转RGB"""
    hex_str = hex_str.lstrip('#')
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))


def parse_color_code(code):
    """解析颜色编码（支持RGB和HEX）"""
    code = code.strip().lower()
    
    # 匹配RGB格式 (r, g, b)
    if code.startswith('rgb'):
        match = re.search(r'\((\d+),\s*(\d+),\s*(\d+)\)', code)
        if match:
            r, g, b = map(int, match.groups())
            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                return (r, g, b)
    
    # 匹配十六进制格式
    elif code.startswith('#') and len(code) in (7, 4):
        try:
            return hex_to_rgb(code)
        except:
            pass
    
    return None


# 填充颜色处理
def choose_fill_color():
    """选择填充颜色"""
    global fill_color
    color = colorchooser.askcolor(title="选择填充颜色", initialcolor=fill_color)
    if color[1]:
        fill_color = tuple(map(int, color[0]))
        update_fill_color_ui()


def apply_fill_color():
    """应用输入的填充颜色编码"""
    global fill_color
    code = fill_color_entry.get()
    color = parse_color_code(code)
    if color:
        fill_color = color
        update_fill_color_ui()
    else:
        messagebox.showwarning("无效输入", "请输入有效的RGB或HEX颜色编码")


def update_fill_color_ui():
    """更新填充颜色UI显示"""
    fill_color_preview.config(bg=rgb_to_hex(fill_color))
    fill_color_entry.delete(0, tk.END)
    fill_color_entry.insert(0, f"rgb{fill_color}")
    status_label.config(text=f"填充色已更新: {rgb_to_hex(fill_color)}")


# 边框设置处理
def choose_border_color():
    """选择边框颜色"""
    global border_color
    color = colorchooser.askcolor(title="选择边框颜色", initialcolor=border_color)
    if color[1]:
        border_color = tuple(map(int, color[0]))
        update_border_color_ui()


def apply_border_color():
    """应用输入的边框颜色编码"""
    global border_color
    code = border_color_entry.get()
    color = parse_color_code(code)
    if color:
        border_color = color
        update_border_color_ui()
    else:
        messagebox.showwarning("无效输入", "请输入有效的RGB或HEX颜色编码")


def update_border_color_ui():
    """更新边框颜色UI显示"""
    border_color_preview.config(bg=rgb_to_hex(border_color))
    border_color_entry.delete(0, tk.END)
    border_color_entry.insert(0, f"rgb{border_color}")
    status_label.config(text=f"边框色已更新: {rgb_to_hex(border_color)}")


def update_border_thickness(value):
    """更新边框厚度"""
    global border_thickness
    border_thickness = value
    border_thickness_label.config(text=str(border_thickness))
    status_label.config(text=f"边框厚度已更新: {border_thickness}px")


# 模式切换
def toggle_annotate_mode():
    """切换填充标注模式"""
    global is_annotating, is_drawing_border
    is_annotating = not is_annotating
    is_drawing_border = False  # 关闭边框模式
    
    if is_annotating:
        annotate_btn.config(text="停止填充标注")
        border_btn.config(text="开始绘制边框")
        canvas.config(cursor="cross")
        status_label.config(text="填充标注模式 - 点击图像区域进行填充")
    else:
        annotate_btn.config(text="开始填充标注")
        canvas.config(cursor="arrow")
        status_label.config(text="已退出填充标注模式")


def toggle_border_mode():
    """切换边框绘制模式"""
    global is_drawing_border, is_annotating
    is_drawing_border = not is_drawing_border
    is_annotating = False  # 关闭填充模式
    
    if is_drawing_border:
        border_btn.config(text="停止绘制边框")
        annotate_btn.config(text="开始填充标注")
        canvas.config(cursor="plus")
        status_label.config(text="边框绘制模式 - 点击图像区域添加边框")
    else:
        border_btn.config(text="开始绘制边框")
        canvas.config(cursor="arrow")
        status_label.config(text="已退出边框绘制模式")


# 阈值设置
def update_threshold(value):
    """更新颜色匹配阈值"""
    global color_threshold
    color_threshold = value
    threshold_label.config(text=str(color_threshold))
    status_label.config(text=f"颜色匹配阈值已更新: {color_threshold}")


# 核心标注功能
def handle_fill_annotation(event):
    """处理填充标注"""
    global current_image
    
    if not current_image:
        return
    
    # 计算原始坐标
    x, y = get_original_coords(event.x, event.y)
    if not is_inside_image(x, y):
        status_label.config(text="点击位置超出图像范围")
        return
    
    # 保存历史记录
    history.append(current_image.copy())
    if len(history) > 50:  # 限制历史记录数量
        history.pop(0)
    
    try:
        # 转换为OpenCV格式
        cv_img = cv2.cvtColor(np.array(current_image), cv2.COLOR_RGB2BGR)
        
        # 泛洪填充
        h, w = cv_img.shape[:2]
        mask = np.zeros((h+2, w+2), np.uint8)
        target_bgr = (fill_color[2], fill_color[1], fill_color[0])  # RGB转BGR
        
        cv2.floodFill(
            cv_img, mask, (x, y), target_bgr,
            (color_threshold, color_threshold, color_threshold),
            (color_threshold, color_threshold, color_threshold),
            cv2.FLOODFILL_FIXED_RANGE
        )
        
        # 转换回PIL格式
        current_image = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        resize_image()
        status_label.config(text="填充标注完成")
    except Exception as e:
        status_label.config(text=f"填充失败: {str(e)}")


def handle_border_drawing(event):
    """处理边框绘制"""
    global current_image
    
    if not current_image:
        return
    
    # 计算原始坐标
    x, y = get_original_coords(event.x, event.y)
    if not is_inside_image(x, y):
        status_label.config(text="点击位置超出图像范围")
        return
    
    # 保存历史记录
    history.append(current_image.copy())
    if len(history) > 50:
        history.pop(0)
    
    try:
        # 获取点击位置的颜色
        cv_img = cv2.cvtColor(np.array(current_image), cv2.COLOR_RGB2BGR)
        target_color = cv_img[y, x].copy()
        
        # 创建掩码（找到相同颜色区域）
        h, w = cv_img.shape[:2]
        mask = np.zeros((h+2, w+2), np.uint8)
        
        # 执行泛洪填充（仅为了创建掩码）
        cv2.floodFill(
            cv_img, mask, (x, y), (0, 0, 0),  # 填充颜色不影响，仅用掩码
            (color_threshold, color_threshold, color_threshold),
            (color_threshold, color_threshold, color_threshold),
            cv2.FLOODFILL_FIXED_RANGE | cv2.FLOODFILL_MASK_ONLY
        )
        
        # 提取掩码并绘制边框
        mask = mask[1:-1, 1:-1]  # 去除边缘
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # 绘制边框（转换为BGR格式）
        border_bgr = (border_color[2], border_color[1], border_color[0])
        cv2.drawContours(cv_img, contours, -1, border_bgr, border_thickness)
        
        # 更新图像
        current_image = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        resize_image()
        status_label.config(text="已为相同颜色区域添加边框")
    except Exception as e:
        status_label.config(text=f"边框绘制失败: {str(e)}")


# 辅助函数
def get_original_coords(display_x, display_y):
    """将显示坐标转换为原始图像坐标"""
    x = int((display_x - canvas_offset[0]) / zoom_factor)
    y = int((display_y - canvas_offset[1]) / zoom_factor)
    return x, y


def is_inside_image(x, y):
    """检查坐标是否在图像范围内"""
    return 0 <= x < original_size[0] and 0 <= y < original_size[1]


def undo():
    """撤销上一步操作"""
    global current_image
    if len(history) > 1:
        history.pop()
        current_image = history[-1].copy()
        resize_image()
        status_label.config(text="已撤销上一步操作")
    else:
        status_label.config(text="已到达初始状态，无法继续撤销")


if __name__ == "__main__":
    main()